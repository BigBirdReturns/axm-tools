# Notice Protocol Amendment 1

## Controlling status

This amendment prospectively supersedes the use of `N1 delivered` in the V4 Notice Standard. The substantive framework is unchanged. The amendment exists because a sender-side sent record cannot establish delivery to a destination-controlled channel.

## Evidence classes

| Code | State | Minimum receipt | What may be claimed | What may not be claimed |
|---|---|---|---|---|
| P0 | Public existence | Persistent public URL or DOI, release date, exact version, artifact hash | The exact object was public by the recorded date | Any particular actor knew of it |
| T0 | Transmitted | Dated sender-side record, destination, route, object, stable link or hash | The sender attempted transmission through the recorded route | Acceptance by the destination |
| N1 | Channel accepted | SMTP server acceptance, portal confirmation, submission ticket, docket receipt, or equivalent destination-controlled evidence | The destination's channel accepted the specified object or link | Human reading, comprehension, or agreement |
| N2 | Acknowledged | Human or automated acknowledgement tied to the transmission | The destination acknowledged receipt | Substantive review |
| N3 | Reviewed | Written response addressing a claim, mechanism, authority, test, or exact ask | The responder engaged substantively | Institutional endorsement unless expressly authorized |
| N4 | Tested | Workshop, exercise, model replication, or pilot record with participants, boundary, and outputs | The claim or mechanism was subjected to the defined test | Validation beyond the test boundary |
| N5 | Inserted | Agenda, working paper, formal submission, funded work package, terms of reference, or docket | The object entered the named formal process | Adoption, implementation, or success |

A negative review, failed exercise, or rejected formal submission remains valid N3, N4, or N5 evidence. The class records engagement rather than approval.

## Channel-acceptance rules

An ordinary copy in a sender's Sent folder is T0. A successful SMTP transaction may qualify as N1 only when the preserved header, server log, or provider record identifies destination acceptance rather than local submission. A web form qualifies as N1 when it returns a confirmation page, ticket, or confirmation email tied to the object. A courier qualifies as N1 when tracking records delivery to the institutional address. A formal portal qualifies as N1 when it issues a submission identifier.

Open tracking pixels and link analytics do not prove human review and should not be used. A read receipt qualifies no higher than N2 and should not be requested where it would be inappropriate.

## Legibility gate

A T0 or N1 record is valid for this programme only when the packet identifies the object class, relevant claim IDs, existing institutional capability, mechanism, antecedent, falsification condition, bounded request, response date, exact public version, and statement that receipt does not imply endorsement.

## Public reporting

The Notice Report counts P0, T0, N1, N2, N3, N4, and N5 separately. It publishes only records marked disclosable. Private responses are summarized only with authorization or at a level that does not identify the responder.
