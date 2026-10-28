"""Deterministic replay and adversarial tests over the actual Atmark capture."""
import copy, csv, hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/catalog.py'); C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
class CatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet=C.read_json(ROOT/'data/observed.json');cls.catalog=C.build(cls.packet)
    def row(self,id):return copy.deepcopy(next(x for x in self.packet['items'] if x['item_id']==id))
    def test_01_all_real_records_accounted(self):
        self.assertEqual(len(self.catalog['items']),53);self.assertEqual(len({x['id'] for x in self.catalog['items']}),53)
    def test_02_original_bytes_semantics_preserved(self):
        for i in self.catalog['items']:self.assertEqual(i['source_hash'],C.digest(i['original']))
    def test_03_source_corrections_exact(self):
        i=C.normalize(self.row('226929518990'));self.assertEqual(len(i['corrections']),2);self.assertIn('Rocket Lake',i['title']);self.assertEqual(i['aspects']['Socket Type'],'FCLGA1200')
    def test_04_wrong_model_image_held(self):
        i=C.normalize(self.row('227473686089'));self.assertIsNone(i['image']);self.assertTrue(any(x['code']=='photo-model-conflict' for x in i['issues']))
    def test_05_prices_never_rewritten(self):
        for i in self.catalog['items']:self.assertEqual((i['price_min'],i['price_max']),(i['original']['price_min'],i['original']['price_max']))
    def test_06_unavailable_stock_kept_explicit(self):
        i=C.normalize(self.row('227552589910'));self.assertEqual(i['availability'],'out-of-stock-observed');self.assertIsNone(i['physical_inventory_id'])
    def test_07_seller_and_id_boundary(self):
        for field,value in [('seller','another-seller'),('item_id','../bad'),('url','https://www.ebay.com/itm/111111111111')]:
            o=self.row('227552589910');o[field]=value
            with self.assertRaises(ValueError):C.normalize(o)
    def test_08_url_host_pins(self):
        for u in ['http://i.ebayimg.com/a','https://i.ebayimg.com.evil.test/a','https://x@i.ebayimg.com/a','file:///etc/passwd','https://i.ebayimg.com:444/a']:
            with self.assertRaises(ValueError):C.checked_url(u,'i.ebayimg.com')
    def test_09_missing_price_not_zero(self):
        for v in [None,'','unknown','-1']:self.assertIsNone(C.money(v))
        self.assertEqual(C.money('0'),0);self.assertEqual(C.money('$1,234.50'),1234.5)
    def test_10_csv_retains_source_and_rejects_bad_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'seller.csv';p.write_bytes(b'\xef\xbb\xbfItem number,Title,Current price,Available quantity,Seller\r\n123456789012,"A, quoted part",,2,atmarktradinginc\r\n123456789013,Wrong seller,10,2,other\r\nbad,Missing id,2,1,\r\n')
            r=C.parse_csv(p);self.assertEqual(len(r['items']),1);self.assertEqual(len(r['coverage']['rejected_rows']),2);self.assertIsNone(r['items'][0]['price_min']);self.assertEqual(r['items'][0]['source_file_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
    def test_11_duplicate_observations_are_visible(self):
        p=copy.deepcopy(self.packet);v=copy.deepcopy(p['items'][0]);v['title']+=' changed';p['items'].append(v);r=C.build(p);self.assertEqual(len(r['items']),53);self.assertEqual(len(r['conflicts']),1)
    def test_12_os_groups_do_not_merge_stock(self):
        self.assertEqual(len(self.catalog['os_groups']),5)
        for g in self.catalog['os_groups']:self.assertGreaterEqual(len(g['ids']),2);self.assertEqual(len(g['ids']),len(set(g['ids'])))
        self.assertEqual(len(self.catalog['items']),53)
    def test_13_gpu_change_does_not_group(self):
        a=self.row('227156017474');b=copy.deepcopy(a);b['item_id']='123456789012';b['url']='https://www.ebay.com/itm/'+b['item_id'];b['title']=b['title'].replace('3090','4090').replace('10','11');p=copy.deepcopy(self.packet);p['items']=[a,b];self.assertEqual(C.build(p)['os_groups'],[])
    def test_14_source_mutation_refuses_acceptance(self):
        p=copy.deepcopy(self.packet);p['items'][0]['price_min']=1;self.assertTrue(C.check(self.catalog,p,ROOT))
    def test_15_false_full_coverage_refused(self):
        c=copy.deepcopy(self.catalog);c['coverage']['complete']=True;self.assertIn('Unproven whole-store coverage',C.check(c,self.packet,ROOT))
    def test_16_live_write_state_refused(self):
        c=copy.deepcopy(self.catalog);c['authority']['live_store_writes']=True;self.assertIn('Live writes enabled',C.check(c,self.packet,ROOT))
    def test_17_csv_formula_safe(self):
        c=copy.deepcopy(self.catalog);c['items'][0]['title']='=HYPERLINK("bad")'
        with tempfile.TemporaryDirectory() as d:
            C.export_files(c,d);rows=list(csv.reader(__import__('io').StringIO((Path(d)/'listing-review.csv').read_text())));self.assertTrue(rows[1][2].startswith("'="))
    def test_18_no_token_no_network(self):
        with patch.object(C,'get_bytes',side_effect=AssertionError('network must not run')):
            with self.assertRaises(ValueError):C.browse('atmarktradinginc','58058','unused',None)
    def test_19_os_pro_not_lost(self):
        self.assertIn('Windows 10 Pro',C.display_title('Dell T5820 W10P'))
    def test_20_missing_canonical_row_refused(self):
        c=copy.deepcopy(self.catalog);c['items'].pop();self.assertIn('Unaccounted source IDs',C.check(c,self.packet,ROOT))
    def test_21_shared_image_collision_is_recorded(self):
        self.assertTrue(any(set(g['ids'])=={'227473686089','226202561474'} for g in self.catalog['shared_images']))
    def test_22_photo_cache_hash_reuse(self):
        b=b'not-a-real-image-but-byte-custody-is-independent';h=hashlib.sha256(b).hexdigest();o=self.row('227543292463');url=o['image_urls'][0]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/(h+'.jpg')).write_bytes(b);C.write_json(p/'source-index.json',{url:{'sha256':h,'local_path':'assets/'+h+'.jpg','source_url':url}})
            with patch.object(C,'get_bytes',side_effect=AssertionError('cache must be used')):r=C.media_collect({'items':[o]},p,0)
            self.assertEqual(r['unique_assets'],1);self.assertEqual(r['failures'],[])
if __name__=='__main__':unittest.main(verbosity=2)
