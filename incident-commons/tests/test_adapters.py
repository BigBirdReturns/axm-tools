# SPDX-License-Identifier: Apache-2.0
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import adapters as ad
import incident as ir

def aws(id, action, t, outcome=None):
    r={"eventID":id,"eventTime":t,"eventName":action,
       "eventSource":"signin.amazonaws.com" if action=="ConsoleLogin" else "iam.amazonaws.com",
       "userIdentity":{"arn":"arn:aws:iam::123456789012:user/test"},
       "sourceIPAddress":"203.0.113.5"}
    if action=="ConsoleLogin":
        r["responseElements"]={"ConsoleLogin":outcome or "Success"}
    return r

class VendorIntakeTests(unittest.TestCase):
    def test_cloudtrail_maps_supported_and_counts_unsupported(self):
        raw=json.dumps({"Records":[
            aws("evt-01","ConsoleLogin","2026-11-16T16:00:00Z","Failure"),
            aws("evt-02","ConsoleLogin","2026-11-16T16:01:00Z","Success"),
            aws("evt-03","CreateAccessKey","2026-11-16T16:02:00Z"),
            aws("evt-04","GetSecretValue","2026-11-16T16:03:00Z"),
            aws("evt-05","DescribeInstances","2026-11-16T16:04:00Z"),
        ]}).encode()
        out,receipt=ad.convert(raw,"aws-cloudtrail","customer-a")
        es=ir.read_events(out)
        self.assertEqual(len(es),4)
        self.assertEqual({x["kind"] for x in es},{"auth_failure","auth_success","token_created","secret_read"})
        self.assertEqual(receipt["skipped"],{"UNMAPPED_EVENT_NAME":1})
        self.assertEqual(receipt["source_sha256"],ir.sha(raw))
        self.assertEqual(receipt["normalized_sha256"],ir.sha(out))
        self.assertTrue(all(e["tenant"]=="customer-a" for e in es))

    def test_entra_signin_success_failure(self):
        raw=json.dumps({"value":[{
            "id":"alpha","createdDateTime":"2026-11-16T16:00:00Z",
            "ipAddress":"198.51.100.8","userPrincipalName":"example@example.test",
            "status":{"errorCode":50126},"resourceDisplayName":"Azure Portal"
        },{
            "id":"beta","createdDateTime":"2026-11-16T16:01:00Z",
            "ipAddress":"198.51.100.8","userPrincipalName":"example@example.test",
            "status":{"errorCode":0},"resourceDisplayName":"Azure Portal"
        }]}).encode()
        out,receipt=ad.convert(raw,"entra-signin","customer-a")
        self.assertEqual([e["kind"] for e in ir.read_events(out)],["auth_failure","auth_success"])
        self.assertEqual(receipt["mapped_count"],2)

    def test_missing_attribution_refused(self):
        raw=json.dumps([{"eventName":"CreateAccessKey","eventTime":"2026-11-16T16:00:00Z",
                         "eventID":"a","sourceIPAddress":"203.0.113.6"}]).encode()
        with self.assertRaisesRegex(ir.Refusal,"SOURCE_MISSING"):
            ad.convert(raw,"aws-cloudtrail","customer-a")

    def test_ambiguous_authentication_refused(self):
        raw=json.dumps([aws("evt-01","ConsoleLogin","2026-11-16T16:00:00Z")]).encode()
        x=json.loads(raw);del x[0]["responseElements"]
        with self.assertRaisesRegex(ir.Refusal,"SOURCE_UNKNOWN"):
            ad.convert(json.dumps(x).encode(),"aws-cloudtrail","customer-a")

    def test_unsupported_source_does_not_invent_events(self):
        raw=json.dumps([aws("evt-01","DescribeInstances","2026-11-16T16:00:00Z")]).encode()
        with self.assertRaisesRegex(ir.Refusal,"NO_MAPPED_EVENTS"):
            ad.convert(raw,"aws-cloudtrail","customer-a")

    def test_bad_tenant_refused(self):
        raw=json.dumps([aws("evt-01","CreateAccessKey","2026-11-16T16:00:00Z")]).encode()
        with self.assertRaisesRegex(ir.Refusal,"BAD_TENANT"):
            ad.convert(raw,"aws-cloudtrail","../../bad")


if __name__=="__main__":
    unittest.main(verbosity=2)
