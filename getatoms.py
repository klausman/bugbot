#!/usr/bin/env python

from __future__ import print_function
import argparse
import base64
import logging
import portage
import requests
import os
import sys

session = requests.Session()


def die(message):
	print(message)
	sys.exit(2)


def eprint(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)


def _bugzilla(path, params):
	try:
		response = session.get('https://bugs.gentoo.org/rest/' + path, params=params).json()
	except Exception as e:
		die('FATAL ERROR: API call failed: {}'.format(e))

	if 'message' in response:
		die('FATAL ERROR: API call failed: {}'.format(response['message']))

	return response


def get_attachments(bug):
	return _bugzilla('bug/{}/attachment'.format(bug), {})['bugs'][str(bug)]


def get_bugs(params):
	return _bugzilla('bug', params)['bugs']


def main():
	'''Get atoms from a stabilisation bug.

	This tool requires a Bugzilla API key to operate, read from the envvar APIKEY.
	Generate one at https://bugs.gentoo.org/userprefs.cgi?tab=apikey
	'''
	# logging.basicConfig(level=logging.DEBUG)

	parser = argparse.ArgumentParser(description=main.__doc__)
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument('--all-bugs', action='store_true', help='process all bugs for the active architecture')
	group.add_argument('-b', '--bug', type=int, help='bug to process')
	parser.add_argument('-a', '--arch', type=str, help='target architecture (defaults to current)')
	parser.add_argument('-n', '--no-depends', action='store_true', help='exclude bugs that depend on other bugs')
	parser.add_argument('-s', '--security', action='store_true', help='fetch only security bugs')
	args = parser.parse_args()

	if 'APIKEY' in os.environ:
		session.params.update({'Bugzilla_api_key': os.environ['APIKEY']})
	else:
		print('FATAL ERROR: Gentoo Bugzilla API key not defined.')
		print('Generate one at https://bugs.gentoo.org/userprefs.cgi?tab=apikey and export in envvar APIKEY.')
		return 2

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
			'f1': 'flagtypes.name',
			'o1': 'equals',
			'v1': 'sanity-check+'
		}

		if args.security is True:
			params['component'] = ['Vulnerabilities']
		else:
			params['component'] = ['Stabilization', 'Vulnerabilities']

	bugs = get_bugs(params)

	return_value = 1
	for bug in bugs:
		if arch_email not in bug['cc']:
			eprint('# {} is not in CC for bug #{}, skipping...'.format(arch, bug['id']))
			eprint()
			continue

		atoms = ''
		if bug['cf_stabilisation_atoms']:
			atoms = bug['cf_stabilisation_atoms']
		else:
			attachments = get_attachments(bug['id'])
			for attachment in attachments:
				if attachment['is_obsolete'] == 1:
					continue

				for flag in attachment['flags']:
					if flag['name'] == 'stabilization-list' and flag['status'] == '+':
						atoms += base64.b64decode(attachment['data']).decode('ascii')

		if not atoms:
			eprint('# No atoms found in bug #{}, skipping...'.format(bug['id']))
			eprint()
			continue

		if bug['depends_on']:
			unresolved_depends = False
			params = {'id': bug['depends_on']}
			depends_bugs = get_bugs(params)

			for depends_bug in depends_bugs:
				if depends_bug['status'] != 'RESOLVED':
					unresolved_depends = True
					break

			if unresolved_depends is True and args.no_depends is True:
				eprint('# bug #{} depends on other unresolved bugs, skipping...'.format(bug['id']))
				eprint()
				continue

		print('# bug #{}'.format(bug['id']))

		for line in atoms.splitlines():
			atom, _, arches = line.partition(' ')
			if not atom.startswith('='):
				atom = '=' + atom

			if not arches or arch in arches.split(' '):
				print(atom)
				return_value = 0

		print()

	return return_value

if __name__ == '__main__':
	sys.exit(main())
