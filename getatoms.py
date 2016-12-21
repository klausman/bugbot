#!/usr/bin/env python

from __future__ import print_function
import argparse
import logging
import portage
import requests
import os
import sys

session = requests.Session()


def die(message):
	print(message)
	sys.exit(2)


def get_bugs(params):
	try:
		response = session.get('https://bugs.gentoo.org/rest/bug', params=params).json()
	except Exception as e:
		die('FATAL ERROR: API call failed: {}'.format(e))

	if 'message' in response:
		die('FATAL ERROR: API call failed: {}'.format(response['message']))

	return response['bugs']


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

		if args.security == True:
			params['component'] = ['Vulnerabilities']
		else:
			params['component'] = ['Stabilization', 'Vulnerabilities']

	bugs = get_bugs(params)

	return_value = 1
	for bug in bugs:
		if arch_email not in bug['cc']:
			print('# {} not in CC, nothing to do'.format(arch))
			continue

		if not bug['cf_stabilisation_atoms']:
			print('# No atoms found, nothing to do')
			continue

		if bug['depends_on']:
			unresolved_depends = False

			params = {'id': bug['depends_on']}
			depends_bugs = get_bugs(params)

			for depends_bug in depends_bugs:
				if depends_bug['status'] != 'RESOLVED':
					unresolved_depends = True
					break
			if unresolved_depends == True and args.no_depends == True:
				print('# This bugs depends on other unresolved bugs, skipping')
				print()
				continue

		print('# bug #{}'.format(bug['id']))

		for line in bug['cf_stabilisation_atoms'].splitlines():
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
