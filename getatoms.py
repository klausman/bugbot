#!/usr/bin/env python

import argparse
import logging
import portage
import requests
import os
import sys


def die(message):
	print(message)
	exit(1)


def get_bugs(params):
	params.update({'Bugzilla_api_key': api})

	try:
		request = requests.get('https://bugs.gentoo.org/rest/bug', params=params).json()
	except Exception as e:
		die('FATAL ERROR: API call failed: {}'.format(e))

	try:
		die('FATAL ERROR: API call failed: {}'.format(request['message']))
	except KeyError:
		pass

	return request['bugs']

if __name__ == '__main__':
	#logging.basicConfig(level=logging.DEBUG)

	parser = argparse.ArgumentParser()
	group = parser.add_mutually_exclusive_group()
	group.add_argument('--all-bugs', action='store_true', help='process all bugs for the active architecture')
	group.add_argument('-b', '--bug', type=int, help='bug to process')
	parser.add_argument('-a', '--arch', type=str, help='target architecture (defaults to current)')
	parser.add_argument('-n', '--no-depends', action='store_true', help='exclude bugs that depend on other bugs')
	parser.add_argument('-s', '--security', action='store_true', help='fetch only security bugs')
	args = parser.parse_args()

	if len(sys.argv) == 1:
		print('Get atoms from a stabilisation bug.')
		print()
		print('This tool requires a Bugzilla API key to operate, read from the envvar APIKEY.')
		print('Generate one at https://bugs.gentoo.org/userprefs.cgi?tab=apikey')
		print()
		parser.print_help()
		sys.exit(1)

	api = os.environ.get('APIKEY')

	if not api:
		print('FATAL ERROR: Gentoo Bugzilla API key not defined.')
		die('Generate one at https://bugs.gentoo.org/userprefs.cgi?tab=apikey and export in envvar APIKEY.')

	if args.arch is None:
		arch = portage.config().get('ARCH')
	else:
		arch = args.arch

	# all bugs
	if args.bug is None:
		params = {
			'resolution': '---',
			'email1': '{}@gentoo.org'.format(arch),
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

	# single bug
	else:
		params = {'id': args.bug}

	bugs = get_bugs(params)

	# extra checks for all bugs
	if len(bugs) == 0:
		die('No available bugs to work on.')

	# extra checks for single bug
	if args.bug is not None:
		bug = bugs[0]
		if not bug['cf_stabilisation_atoms']:
			die('No atoms found in bug #{}'.format(args.bug))

		if bug['depends_on']:
			print('WARNING: bug #{} depends on bug #{}'.format(args.bug, ', '.join(str(x) for x in bug['depends_on'])))

		in_cc = False
		for cc in bug['cc']:
			user, domain = cc.split('@', 1)
			if domain == 'gentoo.org' and user == arch:
				in_cc = True

		if not in_cc:
			die('Current arch ({}) not in CC, nothing to do'.format(arch))

	for bug in bugs:
		list = bug['cf_stabilisation_atoms'].splitlines()

		if bug['depends_on']:
			unresolved_depends = False

			params = {'id': bug['depends_on']}
			depends_bugs = get_bugs(params)

			for depends_bug in depends_bugs:
				if depends_bug['status'] != 'RESOLVED':
					unresolved_depends = True
					break
			if unresolved_depends == True and args.no_depends == True:
				#print('# This bugs depends on other unresolved bugs, skipping')
				#print()
				continue

		print('# bug #{}'.format(bug['id']))

		for item in list:
			if item[0] != '=':
				item = '=' + item
			split = item.split(' ')

			# unqualified atom
			if len(split) == 1:
				print(split[0])
				continue

			# atom qualified with arch
			for part in split[1:]:
				if part == arch:
					print(split[0])

		print()
