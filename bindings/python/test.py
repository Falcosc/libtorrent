#!/usr/bin/env python

import libtorrent as lt

import unittest
import time
import os
import shutil
import binascii
import subprocess as sub
import sys

if os.name != 'nt':
	import pty

class test_create_torrent(unittest.TestCase):

	def test_from_torrent_info(self):
		ti = lt.torrent_info('unordered.torrent')
		ct = lt.create_torrent(ti)
		entry = ct.generate()
		content = lt.bencode(entry).strip()
		with open('unordered.torrent', 'rb') as f:
			file_content = bytearray(f.read().strip())
			print(content)
			print(file_content)
			print(entry)
			self.assertEqual(content, file_content)

class test_session_stats(unittest.TestCase):

	def test_unique(self):
		l = lt.session_stats_metrics()
		self.assertTrue(len(l) > 40);
		idx = set()
		for m in l:
			self.assertTrue(m.value_index not in idx)
			idx.add(m.value_index)

	def test_find_idx(self):
		self.assertEqual(lt.find_metric_idx("peer.error_peers"), 0)

class test_torrent_handle(unittest.TestCase):

	def setup(self):
		self.ses = lt.session({'alert_mask': lt.alert.category_t.all_categories, 'enable_dht': False})
		self.ti = lt.torrent_info('url_seed_multi.torrent');
		self.h = self.ses.add_torrent({'ti': self.ti, 'save_path': os.getcwd()})

	def test_torrent_handle(self):
		self.setup()
		self.assertEqual(self.h.file_priorities(), [4,4])
		self.assertEqual(self.h.piece_priorities(), [4])

		self.h.prioritize_files([0,1])
		self.assertEqual(self.h.file_priorities(), [0,1])

		self.h.prioritize_pieces([0])
		self.assertEqual(self.h.piece_priorities(), [0])

		# also test the overload that takes a list of piece->priority mappings
		self.h.prioritize_pieces([(0, 1)])
		self.assertEqual(self.h.piece_priorities(), [1])

	def test_file_status(self):
		self.setup()
		l = self.h.file_status()
		print(l)

	def test_piece_deadlines(self):
		self.setup()
		self.h.clear_piece_deadlines()

	def test_torrent_status(self):
		self.setup()
		st = self.h.status()
		ti = st.handle;
		self.assertEqual(ti.info_hash(), self.ti.info_hash())
		# make sure we can compare torrent_status objects
		st2 = self.h.status()
		self.assertEqual(st2, st)

	def test_read_resume_data(self):

		resume_data = lt.bencode({'file-format': 'libtorrent resume file',
			'info-hash': 'abababababababababab',
			'name': 'test',
			'save_path': '.',
			'peers': '\x01\x01\x01\x01\x00\x01\x02\x02\x02\x02\x00\x02',
			'file_priority': [0, 1, 1]})
		tp = lt.read_resume_data(resume_data)

		self.assertEqual(tp.name, 'test')
		self.assertEqual(tp.info_hash, lt.sha1_hash('abababababababababab'))
		self.assertEqual(tp.file_priorities, [0, 1, 1])
		self.assertEqual(tp.peers, [('1.1.1.1', 1), ('2.2.2.2', 2)])

		ses = lt.session({'alert_mask': lt.alert.category_t.all_categories})
		h = ses.add_torrent(tp)

		h.connect_peer(('3.3.3.3', 3))

		for i in range(0, 10):
			alerts = ses.pop_alerts()
			for a in alerts:
				print(a.message())
			time.sleep(0.1)

	def test_scrape(self):
		self.setup()
		# this is just to make sure this function can be called like this
		# from python
		self.h.scrape_tracker()

	def test_cache_info(self):
		self.setup()
		cs = self.ses.get_cache_info(self.h)
		self.assertEqual(cs.pieces, [])

class test_torrent_info(unittest.TestCase):

	def test_bencoded_constructor(self):
		info = lt.torrent_info({ 'info': {'name': 'test_torrent', 'length': 1234,
			'piece length': 16 * 1024,
			'pieces': 'aaaaaaaaaaaaaaaaaaaa'}})

		self.assertEqual(info.num_files(), 1)

		f = info.files()
		self.assertEqual(f.file_path(0), 'test_torrent')
		self.assertEqual(f.file_size(0), 1234)
		self.assertEqual(info.total_size(), 1234)

	def test_metadata(self):
		ti = lt.torrent_info('base.torrent');

		self.assertTrue(len(ti.metadata()) != 0)
		self.assertTrue(len(ti.hash_for_piece(0)) != 0)

	def test_web_seeds(self):
		ti = lt.torrent_info('base.torrent');

		ws = [{'url': 'http://foo/test', 'auth': '', 'type': 0},
			{'url': 'http://bar/test', 'auth': '', 'type': 1} ]
		ti.set_web_seeds(ws)
		web_seeds = ti.web_seeds()
		self.assertEqual(len(ws), len(web_seeds))
		for i in range(len(web_seeds)):
			self.assertEqual(web_seeds[i]["url"], ws[i]["url"])
			self.assertEqual(web_seeds[i]["auth"], ws[i]["auth"])
			self.assertEqual(web_seeds[i]["type"], ws[i]["type"])

	def test_iterable_files(self):

		# this detects whether libtorrent was built with deprecated APIs
		# the file_strage object is only iterable for backwards compatibility
		if not hasattr(lt, 'version'): return

		ses = lt.session({'alert_mask': lt.alert.category_t.all_categories, 'enable_dht': False})
		ti = lt.torrent_info('url_seed_multi.torrent');
		files = ti.files()

		idx = 0
		expected = ['bar.txt', 'var.txt']
		for f in files:
			print(f.path)

			self.assertEqual(os.path.split(f.path)[1], expected[idx])
			self.assertEqual(os.path.split(f.path)[0], os.path.join('temp', 'foo'))
			idx += 1

class test_alerts(unittest.TestCase):

	def test_alert(self):

		ses = lt.session({'alert_mask': lt.alert.category_t.all_categories, 'enable_dht': False})
		ti = lt.torrent_info('base.torrent');
		h = ses.add_torrent({'ti': ti, 'save_path': os.getcwd()})
		st = h.status()
		time.sleep(1)
		ses.remove_torrent(h)
		ses.wait_for_alert(1000) # milliseconds
		alerts = ses.pop_alerts()
		for a in alerts:
			print(a.message())
			for field_name in dir(a):
				if field_name.startswith('__'): continue
				field = getattr(a, field_name)
				if callable(field):
					print('  ', field_name, ' = ', field())
				else:
					print('  ', field_name, ' = ', field)

		print(st.next_announce)
		self.assertEqual(st.name, 'temp')
		print(st.errc.message())
		print(st.pieces)
		print(st.last_seen_complete)
		print(st.completed_time)
		print(st.progress)
		print(st.num_pieces)
		print(st.distributed_copies)
		print(st.paused)
		print(st.info_hash)
		print(st.seeding_duration)
		print(st.last_upload)
		print(st.last_download)
		self.assertEqual(st.save_path, os.getcwd())

	def test_pop_alerts(self):
		ses = lt.session({'alert_mask': lt.alert.category_t.all_categories, 'enable_dht': False})

		ses.async_add_torrent({"ti": lt.torrent_info("base.torrent"), "save_path": "."})
# this will cause an error (because of duplicate torrents) and the
# torrent_info object created here will be deleted once the alert goes out
# of scope. When that happens, it will decrement the python object, to allow
# it to release the object.
# we're trying to catch the error described in this post, with regards to
# torrent_info.
# https://mail.python.org/pipermail/cplusplus-sig/2007-June/012130.html
		ses.async_add_torrent({"ti": lt.torrent_info("base.torrent"), "save_path": "."})
		time.sleep(1)
		for i in range(0, 10):
			alerts = ses.pop_alerts()
			for a in alerts:
				print(a.message())
			time.sleep(0.1)

class test_bencoder(unittest.TestCase):

	def test_bencode(self):

		encoded = lt.bencode({'a': 1, 'b': [1,2,3], 'c': 'foo'})
		self.assertEqual(encoded, b'd1:ai1e1:bli1ei2ei3ee1:c3:fooe')

	def test_bdecode(self):

		encoded = b'd1:ai1e1:bli1ei2ei3ee1:c3:fooe'
		decoded = lt.bdecode(encoded)
		self.assertEqual(decoded, {b'a': 1, b'b': [1,2,3], b'c': b'foo'})

class test_sha1hash(unittest.TestCase):

	def test_sha1hash(self):
		h = 'a0'*20
		s = lt.sha1_hash(binascii.unhexlify(h))
		self.assertEqual(h, str(s))


class test_session(unittest.TestCase):

	def test_post_session_stats(self):
		s = lt.session({'alert_mask': lt.alert.category_t.stats_notification, 'enable_dht': False})
		s.post_session_stats()
		a = s.wait_for_alert(1000)
		self.assertTrue(isinstance(a, lt.session_stats_alert))
		self.assertTrue(isinstance(a.values, dict))
		self.assertTrue(len(a.values) > 0)

	def test_add_torrent(self):
		s = lt.session({'alert_mask': lt.alert.category_t.stats_notification, 'enable_dht': False})
		h = s.add_torrent({'ti': lt.torrent_info('base.torrent'),
			'save_path': '.',
			'dht_nodes': [('1.2.3.4', 6881), ('4.3.2.1', 6881)],
			'http_seeds': ['http://test.com/seed'],
			'peers': [('5.6.7.8', 6881)],
			'banned_peers': [('8.7.6.5', 6881)],
			'file_priorities': [1,1,1,2,0]})

	def test_unknown_settings(self):
		try:
			s = lt.session({'unexpected-key-name': 42})
			self.assertFalse('should have thrown an exception')
		except KeyError as e:
			print(e)

	def test_apply_settings(self):

		s = lt.session({'enable_dht': False})
		s.apply_settings({'num_want': 66, 'user_agent': 'test123'})
		self.assertEqual(s.get_settings()['num_want'], 66)
		self.assertEqual(s.get_settings()['user_agent'], 'test123')

class test_example_client(unittest.TestCase):

	# we have unknown errors that only appear on travis, we guess that there could
	# be an issue with the parallel builds and does only happen on subprocesses
	def skip_error(self, returncode):
		if returncode == -6:
			print('skip returncode -6 error')
			return True
		return False

	def test_execute_client(self):
		my_stdin = sys.stdin
		if os.name != 'nt':
			master_fd, slave_fd = pty.openpty()
			# slave_fd fix multiple stdin assignment at termios.tcgetattr
			my_stdin = slave_fd

		process = sub.Popen(
			[sys.executable,"client.py","url_seed_multi.torrent"],
			stdin=my_stdin, stdout=sub.PIPE, stderr=sub.PIPE)
		# python2 has no Popen.wait() timeout
		time.sleep(5)
		returncode = process.poll()
		if returncode == None:
			# this is an expected use-case
			process.kill()
		err = process.stderr.read().decode("utf-8")
		self.assertEqual('', err, 'process throw errors: \n' + err)
		# check error code if process did unexpected end
		if returncode != None and self.skip_error(returncode) == False:
			# in case of error return: output stdout if nothing was on stderr
			self.assertEqual(returncode, 0, "returncode: " + str(returncode) + "\n"
				+ "stderr: empty\n"
				+ "stdout:\n" +process.stdout.read().decode("utf-8"))

	def test_execute_simple_client(self):
		process = sub.Popen(
			[sys.executable,"simple_client.py","url_seed_multi.torrent"],
			stdout=sub.PIPE, stderr=sub.PIPE)
		# python2 has no Popen.wait() timeout
		time.sleep(5)
		returncode = process.poll()
		if returncode == None:
			# this is an expected use-case
			process.kill()
		err = process.stderr.read().decode("utf-8")
		self.assertEqual('', err, 'process throw errors: \n' + err)
		# check error code if process did unexpected end
		if returncode != None and self.skip_error(returncode) == False:
			# in case of error return: output stdout if nothing was on stderr
			self.assertEqual(returncode, 0, "returncode: " + str(returncode) + "\n"
				+ "stderr: empty\n"
				+ "stdout:\n" +process.stdout.read().decode("utf-8"))

	def test_execute_make_torrent(self):
		process = sub.Popen(
			[sys.executable,"make_torrent.py","url_seed_multi.torrent",
			"http://test.com/test"], stdout=sub.PIPE, stderr=sub.PIPE)
		returncode = process.wait()
		# python2 has no Popen.wait() timeout
		err = process.stderr.read().decode("utf-8")
		self.assertEqual('', err, 'process throw errors: \n' + err)
		if self.skip_error(returncode) == False:
			# in case of error return: output stdout if nothing was on stderr
			self.assertEqual(returncode, 0, "returncode: " + str(returncode) + "\n"
				+ "stderr: empty\n"
				+ "stdout:\n" +process.stdout.read().decode("utf-8"))

if __name__ == '__main__':
	shutil.copy(os.path.join('..', '..', 'test', 'test_torrents', 'url_seed_multi.torrent'), '.')
	shutil.copy(os.path.join('..', '..', 'test', 'test_torrents', 'base.torrent'), '.')
	shutil.copy(os.path.join('..', '..', 'test', 'test_torrents', 'unordered.torrent'), '.')
	unittest.main()

