import json

from sendgrid.helpers.endpoints.ip.unassigned import unassigned

ret_json = '''[ {
	"ip": "167.89.21.3",
        "pools": [
		"pool1",
	"pool2"
	],
        "whitelabeled": false,
        "start_date": 1409616000,
        "subusers": [
          "tim@sendgrid.net"
        ],
        "warmup": false,
        "assigned_at": 1482883200
      },
      {
        "ip": "192.168.1.1",
        "pools": [
          "pool1",
          "pool2"
        ],
        "whitelabeled": false,
        "start_date": 1409616000,
        "subusers": [
          "tim@sendgrid.net"
        ],
        "warmup": false,
        "assigned_at": 1482883200
      },
      {
        "ip": "208.115.214.22",
        "pools": [],
        "whitelabeled": true,
        "rdns": "o1.email.burgermail.com",
        "start_date": 1409616000,
        "subusers": [],
        "warmup": false,
        "assigned_at": 1482883200
      },
      {
        "ip": "208.115.214.23",
        "pools": [],
        "whitelabeled": true,
        "rdns": "o1.email.burgermail.com",
        "start_date": 1409616000,
        "subusers": [],
        "warmup": false,
        "assigned_at": 1482883200

      } ]
      '''


def get_all_ip():
    ret_val = json.loads(ret_json)
    return ret_val


def make_data():
    data = set()
    data.add("208.115.214.23")
    data.add("208.115.214.22")
    return data


def test_unassigned_ip_json():
    data = make_data()

    as_json = True
    calculated = unassigned(get_all_ip(), as_json=as_json)
    calculated = json.loads(calculated)

    for item in calculated:
        assert item["ip"] in data


def test_unassigned_ip_obj():
    data = make_data()

    as_json = False
    calculated = unassigned(get_all_ip(), as_json=as_json)

    for item in calculated:
        assert item["ip"] in data


def test_unassigned_baddata():
    as_json = False
    calculated = unassigned(dict(), as_json=as_json)
    assert calculated == []
