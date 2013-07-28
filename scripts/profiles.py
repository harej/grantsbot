#! /usr/bin/env python2.7

# Copyright 2013 Jtmorgan

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# from wikitools import category as wtcat
from datetime import datetime, timedelta
import dateutil.parser
import wikitools
import grantsbot_settings
import templates
import operator
import pages
import re

class Profiles:
	"""A grab-bag of operations you might want to perform on and with profiles."""

	def __init__(self, path, type, id = False, namespace = grantsbot_settings.rootpage):
		"""
		Instantiates page-level variables for building a set of profiles.
		"""
		self.page_path = path
		self.page_id = str(id)
# 		print self.page_id
		self.type = type
		self.namespace = namespace #used for people, not ideas
		self.wiki = wikitools.Wiki(grantsbot_settings.apiurl)
		self.wiki.login(grantsbot_settings.username, grantsbot_settings.password)

	def getPageSectionData(self):
		"""
		Returns the section titles and numbers for a given page.
		Sample request: http://meta.wikimedia.org/w/api.php?action=parse&page=Grants:IdeaLab/Introductions&prop=sections&format=jsonfm
		"""
		params = {
			'action': 'parse',
			'page': self.page_path,
			'prop': 'sections',
		}
		req = wikitools.APIRequest(self.wiki, params)
		response = req.query()
		secs_list = [{'username' : x['line'], 'profile index' : x['index']} for x in response['parse']['sections']] #username here should be made agnostic, so title
		return secs_list

	def getPageText(self, section = False):
		"""
		Gets the raw text of a page or page section.
		Sample: http://meta.wikimedia.org/w/api.php?action=query&prop=revisions&titles=Grants:IdeaLab/Introductions&rvprop=content&rvsection=21&format=jsonfm
		"""
		params = {
			'action': 'query',
			'prop': 'revisions',
			'titles': self.page_path,
			'rvprop' : 'content',
			'rvsection' : section,
		}
		req = wikitools.APIRequest(self.wiki, params)
		response = req.query()
		text = response['query']['pages'][self.page_id]['revisions'][0]['*']
		return text

	def getPageInfo(self, val, prop, talkpage = False):
		"""
		Retrieve the default page info metadata OR latest revision metadata.
		Sample:
http://meta.wikimedia.org/w/api.php?action=query&prop=info&titles=Grants:IEG/GIS_and_Cartography_in_Wikimedia&format=jsonfm
		"""
		params = {
			'action': 'query',
			'prop': prop,
		}
		if talkpage:
			page_id = str(talkpage)
			params['pageids'] = page_id			
		else:
			params['titles'] = self.page_path
			page_id = self.page_id	
		req = wikitools.APIRequest(self.wiki, params)
		response = req.query()
		if prop == 'info':
			info = response['query']['pages'][page_id][val]
		elif prop =='revisions':
			info = response['query']['pages'][page_id]['revisions'][0][val]
		else:
			print "invalid prop parameter specified"
		return info

	def getPageRecentEditInfo(self, timestring, pages=False, people=False):
		"""
		Gets timestamp and user id for recent revisions from a page, based on a timestamp you specify as a string.
		Example: http://meta.wikimedia.org/w/api.php?action=query&prop=revisions&pageids=2275494&rvdir=newer&rvstart=20130601000000&rvprop=timestamp|userid&format=jsonfm
		"""
		params = {
			'action': 'query',
			'prop': 'revisions',
			'pageids': '',
			'rvdir': 'newer',
			'rvstart' : timestring,
			'rvprop' : 'timestamp|user|userid|comment|talkid',
		}
		recent_editors = []
		if pages:
			for page in pages:
				params['pageids'] = page
				req = wikitools.APIRequest(self.wiki, params)
				response = req.query()
				try:
					edits = response['query']['pages'][params['pageids']]['revisions']
# 					print edits
					editors = [x['userid'] for x in edits]
					recent_editors.extend(editors)
				except: #if no revisions, no recent editors, no talkpageid
					pass
			recent_editors = list(set([x for x in recent_editors])) #remove duplicates
		elif people:
			suffix = "new section"
			params['pageids'] = self.page_id
			req = wikitools.APIRequest(self.wiki, params)
			response = req.query()
			try:
				edits = response['query']['pages'][params['pageids']]['revisions']
				for edit in edits:
					if edit['comment'].endswith(suffix):
						intro = {'creator' : edit['user'], 'datetime added' : edit['timestamp'], 'action' : 5}
						recent_editors.append(intro)
			except KeyError: #if no revisions, no recent editors
				pass
		else:
			print "Need list of pageids or specify that you want person profiles."
		return recent_editors

	def getUserRecentEditInfo(self, user_name, edit_namespace = False): #rename
		"""
		Get edits by a user in a given namespace within the past month, and the time of their most recent edit.
		Sample: http://meta.wikimedia.org/w/api.php?action=query&list=recentchanges&rcnamespace=200&rcuser=Jmorgan_(WMF)&rclimit=500&format=jsonfm
		"""
		params = { #need to update this so that it will accept recent edits, or first edit to the page (page edits by user sorted in reverse date order)
			'action': 'query',
			'list': 'recentchanges',
			'rcuser': user_name,
			'rcnamespace': edit_namespace,
		}
		req = wikitools.APIRequest(self.wiki, params)
		response = req.query()
		recent_edits = len(response['query']['recentchanges'])
		if recent_edits > 0:
			latest_edit = response['query']['recentchanges'][0]['timestamp']
			latest_rev = response['query']['recentchanges'][0]['revid']
			edit_info = (recent_edits, latest_rev, latest_edit)
		else:
			edit_info = (0, 0, "")
		return edit_info

	def formatProfile(self, val):
		"""
		takes in a dictionary of parameter values and plugs them into the specified template
		"""
		page_templates = templates.Template()
		tmplt = page_templates.getTemplate(self.type)
		tmplt = tmplt.format(**val).encode('utf-8')
		return tmplt

	def publishProfile(self, val, path, edit_summ, sb_page = False, edit_sec = False):
		"""
		Publishes a profile or set of concatenated profiles to a page on a wiki.
		"""
		if sb_page:
			path += str(sb_page)			
# 		print path
# 		print val
# 		print edit_summ
		output = wikitools.Page(self.wiki, path)
		if edit_sec:
			output.edit(val, section=edit_sec, summary=edit_summ, bot=1)
		else:
			output.edit(val, summary=edit_summ, bot=1) #not ideal
		
			

class Toolkit:
	"""
	Handy ready-to-use methods that you don't need to create a complex object for.
	"""

	def getSubDate(self, day_interval, pretty=False):
		"""
		Returns the date a specified number of days before the current date as an API and database-friendly 14-digit timestamp string. Also handy for getting a date formatted for pretty output.
		"""
		date_since = datetime.utcnow()-timedelta(days=day_interval)
		if pretty:
			date_since = date_since.strftime('%m/%d/%y')
		else:
			date_since = date_since.strftime('%Y%m%d%H%M%S')
		return date_since

	def parseISOtime(self, iso):
		"""
		Parses the ISO datetime values returned by the API into strings.
		"""
		date_str = dateutil.parser.parse(iso).strftime('%x')
		return date_str

	def formatSummaries(self, text):
		"""
		Cleans markup from strings of profile summary text and trims them to 140 chars.
		"""
		text = text.strip()
		text = re.sub("(\[\[)(.*?)(\|)","",text)
		text = re.sub("\]","",text)
		text = re.sub("\[","",text)
		text = (text[:140] + '...') if len(text) > 140 else text
		return text

	def dedupeMemberList(self, mem_list, sort_val, dict_val):
		"""
		Sort and remove duplicates from a list of dicts based on a specified key/value pair. Also removes things that should be ignored.
		"""
		mem_list.sort(key=operator.itemgetter(sort_val), reverse=True)
		seen_list = ['Grants:IdeaLab/Preload']
		unique_list = []
		for mem in mem_list:
			t = mem[dict_val]
			if t not in seen_list:
				seen_list.append(t)
				unique_list.append(mem)
			else:
				pass
		return unique_list
	
	def compareDates(self, date_one, date_two):
		"""
		Compares to date strings and returns the most recent one.
		"""
		one = datetime.strptime(date_one, "%m/%d/%y")
		two = datetime.strptime(date_two, "%m/%d/%y")
		if one >= two:
			return date_one
		else:
			return date_two			
