#!/usr/bin/env python

from __future__ import print_function
import argparse
import base64
import logging
import requests
import os
import sys
import xmlrpc.client

file = None
session = requests.Session()


def die(message):
	print(message)
	sys.exit(2)


def error(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)

def eprint(message):
	print(message)

	if file is not None:
		file.write(message + '\n')

def _bugzilla(path, params):
	try:
		response = session.get('https://bugs.gentoo.org/rest/' + path, params=params).json()
	except Exception as e:
		die('FATAL ERROR: API call failed: {}'.format(e))

	if 'message' in response:
		die('FATAL ERROR: API call failed: {}'.format(response['message']))

	return response


def get_bugs(params):
	return _bugzilla('bug', params)['bugs']


def main():
	'''Get atoms from a stabilisation bug.

	This tool requires a Bugzilla API key to operate, read from the envvar APIKEY.
	Generate one at https://bugs.gentoo.org/userprefs.cgi?tab=apikey

	If the variable TESTFILE is defined, the batch_stabilize-compatible output will be written to that file.
	'''
	# logging.basicConfig(level=logging.DEBUG)

	parser = argparse.ArgumentParser(description=main.__doc__)
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument('--all-bugs', action='store_true', help='process all bugs for the active architecture')
	group.add_argument('-b', '--bug', type=int, help='bug to process')
	group.add_argument('-s', '--security', action='store_true', help='fetch only security bugs')
	buggroup = parser.add_mutually_exclusive_group()
	buggroup.add_argument('--keywordreq', action='store_true', help='work on keywording bugs')
	buggroup.add_argument('--stablereq', action='store_true', help='work on stabilisation bugs')
	parser.add_argument('-a', '--arch', type=str, help='target architecture (defaults to current)')
	parser.add_argument('-n', '--no-depends', action='store_true', help='exclude bugs that depend on other bugs')
	parser.add_argument('--no-sanity-check', action='store_true', help='include bugs that are not marked as sanity checked')
	args = parser.parse_args()

	if args.all_bugs is True and args.keywordreq is False and args.stablereq is False:
		print('--all-bugs must be called with one of --keywordreq or --stablereq')
		return 2

	if 'APIKEY' in os.environ:
		session.params.update({'Bugzilla_api_key': os.environ['APIKEY']})
	else:
		print('FATAL ERROR: Gentoo Bugzilla API key not defined.')
		print('Generate one at https://bugs.gentoo.org/userprefs.cgi?tab=apikey and export in envvar APIKEY.')
		return 2

	if 'TESTFILE' in os.environ:
		global file
		file = open(os.environ['TESTFILE'], 'w')

	arch = args.arch
	if not arch:
		# This is usually frowned upon, but portage is heavy, so only import it if necessary
		import portage
		arch = portage.config().get('ARCH')

	arch_email = arch + '@gentoo.org'

	if args.bug:
		params = {'id': args.bug}
	else:
		params = {
			'resolution': '---',
			'email1': arch_email,
			'emailassigned_to1': 1,
			'emailcc1': 1,
			'emailtype1': 'equals',
		}

		if args.no_sanity_check is not True:
			params['f1'] = 'flagtypes.name'
			params['o1'] = 'equals'
			params['v1'] ='sanity-check+'

		if args.keywordreq is True:
			params['component'] = ['Keywording']
		elif args.stablereq is True:
			params['component'] = ['Stabilization', 'Vulnerabilities']
		elif args.security is True:
			params['component'] = ['Vulnerabilities']
	bugs = get_bugs(params)
	depends_bugs = []

	for bug in bugs:
		depends_bugs += bug['depends_on']

	# otherwise, id == '' which will query every single bug ever filed
	if len(depends_bugs) >= 1:
		params = { 'id': depends_bugs }
		depends_bugs = get_bugs(params)

	depends_bugs_dict = {}
	for bug in depends_bugs:
		depends_bugs_dict[bug['id']] = bug

	all_attachments = xmlrpc.client.ServerProxy('https://bugs.gentoo.org/xmlrpc.cgi').Bug.attachments({'ids': [ x['id'] for x in bugs ] })['bugs']
	return_value = 1
	for bug in bugs:
		if arch_email not in bug['cc']:
			error('# {} is not in CC for bug #{}, skipping...'.format(arch, bug['id']))
			error()
			continue

		atoms = ''
		if bug['cf_stabilisation_atoms']:
			atoms += bug['cf_stabilisation_atoms']

		for attachment in all_attachments[str(bug['id'])]:
			if not attachment:
				continue
			if attachment['is_obsolete'] == 1:
				continue

			for flag in attachment['flags']:
				if flag['name'] == 'stabilization-list' and flag['status'] == '+':
					if atoms and atoms[-1] is not "\n":
						atoms += "\n"
					atoms += str(attachment['data'])

		if not atoms:
			error('# No atoms found in bug #{}, skipping...'.format(bug['id']))
			error()
			continue

		if bug['depends_on']:
			unresolved_depends = False

			for depends_bug in bug['depends_on']:
				current_bug = depends_bugs_dict[depends_bug]

				if current_bug['status'] == 'RESOLVED':
					continue

				if current_bug['component'] in ['Stabilization', 'Keywording', 'Vulnerabilities']:

					sanity_checked = False
					for flag in current_bug['flags']:
						if flag['name'] == 'sanity-check' and flag['status'] == '+':
							sanity_checked = True
							break

					if arch_email not in current_bug['cc'] and sanity_checked:
							continue

				unresolved_depends = True
				break

			if unresolved_depends is True and args.no_depends is True:
				error('# bug #{} depends on other unresolved bugs, skipping...'.format(bug['id']))
				error()
				continue

		eprint('# bug #{}'.format(bug['id']))

		atoms_to_print = set()
		for line in atoms.splitlines():
			if not line:
				continue
			atom, _, arches = line.partition(' ')
			if not atom.startswith('='):
				atom = '=' + atom

			if not arches or arch in arches.split(' ') or '~' + arch in arches.split(' '):
				atoms_to_print.add(atom)
				return_value = 0
		eprint("\n".join(sorted(atoms_to_print)))

		eprint('')

	if 'TESTFILE' in os.environ:
		file.close()

	return return_value

if __name__ == '__main__':
	sys.exit(main())
