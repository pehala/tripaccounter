"""Functional tests for label creation, normalization, and listing."""


def test_label_auto_created_on_item_write(client, trip, item_body):
    """Writing an item with an unknown label creates it on the fly."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["street-food"]))

    labels = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"]
    assert [label["name"] for label in labels] == ["street-food"]
    assert labels[0]["use_count"] == 1


def test_label_casing_and_whitespace_collapse_to_one(client, trip, scenario_items):
    """Food / food / ' food ' all collapse to the same label."""
    labels = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"]
    food = next(label for label in labels if label["name"] == "Food")
    assert food["use_count"] == 3


def test_label_with_whitespace_is_422(client, trip, item_body):
    """A token with an inner space is rejected, not split."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["street food"])
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["labels"]["code"] == "label_whitespace"


def test_label_list_orders_by_use_count_desc_then_name(client, trip, scenario_items):
    """Labels list use_count DESC, name ASC: Food(3), b(2), then a/dining/fun tied at 1."""
    labels = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"]
    assert [label["name"] for label in labels] == ["Food", "b", "a", "dining", "fun"]


def test_use_count_tracks_detach_and_item_delete(client, trip, item_body):
    """use_count decreases when a label is removed from an item, and on item delete."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food"])
    ).json()["item"]
    assert client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"][0]["use_count"] == 1

    client.patch(f"/api/v1/trips/{trip['slug']}/items/{item['id']}", json={"labels": []})
    assert client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"][0]["use_count"] == 0

    item2 = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food"])
    ).json()["item"]
    client.delete(f"/api/v1/trips/{trip['slug']}/items/{item2['id']}")
    assert client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"][0]["use_count"] == 0


def test_delete_label_leaves_items_untouched(client, trip, item_body):
    """Deleting a label removes only the association; the item survives."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food"])
    ).json()["item"]
    label_id = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"][0]["id"]

    response = client.delete(f"/api/v1/trips/{trip['slug']}/labels/{label_id}")
    assert response.status_code == 204

    read_back = client.get(f"/api/v1/trips/{trip['slug']}/items/{item['id']}").json()["item"]
    assert read_back["labels"] == []


def test_item_labels_are_alphabetical_on_create(client, trip, item_body):
    """A created item answers with its labels alphabetical, whatever order they were sent."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["zulu", "alpha", "mike"])
    ).json()["item"]

    assert item["labels"] == ["alpha", "mike", "zulu"]


def test_item_labels_are_alphabetical_on_update(client, trip, item_body):
    """Re-labelling an item answers with the new labels alphabetical."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["alpha"])
    ).json()["item"]

    updated = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{item['id']}", json={"labels": ["yankee", "bravo"]}
    ).json()["item"]

    assert updated["labels"] == ["bravo", "yankee"]


def test_item_labels_are_alphabetical_on_read(client, trip, item_body):
    """Reading an item back answers with its labels alphabetical."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["zulu", "alpha", "mike"])
    ).json()["item"]

    read_back = client.get(f"/api/v1/trips/{trip['slug']}/items/{item['id']}").json()["item"]

    assert read_back["labels"] == ["alpha", "mike", "zulu"]


def test_create_label_starts_unused(client, trip):
    """A label created directly exists with use_count 0, attached to nothing."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/labels", json={"name": "street-food"})

    assert response.status_code == 201, response.text
    label = response.json()["label"]
    assert label["name"] == "street-food"
    assert label["use_count"] == 0


def test_create_label_that_normalizes_onto_an_existing_one_is_409(client, trip, item_body):
    """A label whose normalized form is already taken conflicts, whatever its casing."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food"]))

    response = client.post(f"/api/v1/trips/{trip['slug']}/labels", json={"name": "Food"})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {"name": {"code": "duplicate", "params": {"name": "Food"}}},
        }
    }


def test_rename_label_keeps_it_attached_to_its_items(client, trip, item_body):
    """A renamed label keeps its use count and the items already carrying it."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food"])
    ).json()["item"]
    label_id = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"][0]["id"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/labels/{label_id}", json={"name": "dining"}
    )

    assert response.status_code == 200
    assert response.json()["label"]["name"] == "dining"
    assert response.json()["label"]["use_count"] == 1
    read_back = client.get(f"/api/v1/trips/{trip['slug']}/items/{item['id']}").json()["item"]
    assert read_back["labels"] == ["dining"]


def test_rename_label_onto_another_label_is_409(client, trip, item_body):
    """Renaming a label onto a name the trip already holds conflicts."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food", "fun"]))
    labels = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"]
    food = next(label for label in labels if label["name"] == "food")

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/labels/{food['id']}", json={"name": "fun"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["fields"]["name"] == {
        "code": "duplicate",
        "params": {"name": "fun"},
    }


def test_patch_label_without_a_name_leaves_it_alone(client, trip):
    """A PATCH carrying no name is accepted and changes nothing."""
    label = client.post(f"/api/v1/trips/{trip['slug']}/labels", json={"name": "food"}).json()[
        "label"
    ]

    response = client.patch(f"/api/v1/trips/{trip['slug']}/labels/{label['id']}", json={})

    assert response.status_code == 200
    assert response.json()["label"] == label


def test_one_item_carrying_a_label_twice_counts_it_once(client, trip, item_body):
    """Two tokens that normalize the same on one item make one label used once."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["food", "Food"])
    ).json()["item"]

    labels = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"]
    assert item["labels"] == ["food"]
    assert [(label["name"], label["use_count"]) for label in labels] == [("food", 1)]


def test_relabelling_an_item_moves_only_the_labels_that_changed(client, trip, item_body):
    """Re-labelling drops the use count of what left, raises what arrived, keeps what stayed."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(labels=["alpha", "bravo"])
    ).json()["item"]

    client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{item['id']}", json={"labels": ["bravo", "charlie"]}
    )

    labels = client.get(f"/api/v1/trips/{trip['slug']}/labels").json()["labels"]
    assert {label["name"]: label["use_count"] for label in labels} == {
        "alpha": 0,
        "bravo": 1,
        "charlie": 1,
    }
