"""Functional tests for label creation, normalization, and listing."""


def test_label_auto_created_on_item_write(client, trip_url, item_body, create):
    """Writing an item with an unknown label creates it on the fly."""
    create("items", item_body(labels=["street-food"]))

    labels = client.get(f"{trip_url}/labels").json()["labels"]
    assert [label["name"] for label in labels] == ["street-food"]
    assert labels[0]["use_count"] == 1


def test_label_casing_and_whitespace_collapse_to_one(client, trip_url, scenario_items):
    """Food / food / ' food ' all collapse to the same label."""
    labels = client.get(f"{trip_url}/labels").json()["labels"]
    food = next(label for label in labels if label["name"] == "Food")
    assert food["use_count"] == 3


def test_label_with_whitespace_is_422(client, trip_url, item_body):
    """A token with an inner space is rejected, not split."""
    response = client.post(f"{trip_url}/items", json=item_body(labels=["street food"]))
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["labels"]["code"] == "label_whitespace"


def test_label_list_orders_by_use_count_desc_then_name(client, trip_url, scenario_items):
    """Labels list use_count DESC, name ASC: Food(3), b(2), then a/dining/fun tied at 1."""
    labels = client.get(f"{trip_url}/labels").json()["labels"]
    assert [label["name"] for label in labels] == ["Food", "b", "a", "dining", "fun"]


def test_label_is_deleted_when_its_last_item_stops_using_it(client, trip_url, item_body, create):
    """Detaching a label from its only item, or deleting that item, removes the label."""
    item = create("items", item_body(labels=["food"]))
    assert [label["use_count"] for label in client.get(f"{trip_url}/labels").json()["labels"]] == [
        1
    ]

    client.patch(f"{trip_url}/items/{item['id']}", json={"labels": []})
    assert client.get(f"{trip_url}/labels").json()["labels"] == []

    item2 = create("items", item_body(labels=["food"]))
    client.delete(f"{trip_url}/items/{item2['id']}")
    assert client.get(f"{trip_url}/labels").json()["labels"] == []


def test_label_survives_while_another_item_uses_it(client, trip_url, item_body, create):
    """A label dropped from one item stays, with its count lowered, while another item has it."""
    item = create("items", item_body(labels=["food"]))
    create("items", item_body(labels=["food"]))

    client.patch(f"{trip_url}/items/{item['id']}", json={"labels": []})

    labels = client.get(f"{trip_url}/labels").json()["labels"]
    assert [(label["name"], label["use_count"]) for label in labels] == [("food", 1)]


def test_delete_label_leaves_items_untouched(client, trip_url, item_body, create):
    """Deleting a label removes only the association; the item survives."""
    item = create("items", item_body(labels=["food"]))
    label_id = client.get(f"{trip_url}/labels").json()["labels"][0]["id"]

    response = client.delete(f"{trip_url}/labels/{label_id}")
    assert response.status_code == 204

    read_back = client.get(f"{trip_url}/items/{item['id']}").json()["item"]
    assert read_back["labels"] == []


def test_item_labels_are_alphabetical_on_create(item_body, create):
    """A created item answers with its labels alphabetical, whatever order they were sent."""
    item = create("items", item_body(labels=["zulu", "alpha", "mike"]))

    assert item["labels"] == ["alpha", "mike", "zulu"]


def test_item_labels_are_alphabetical_on_update(client, trip_url, item_body, create):
    """Re-labelling an item answers with the new labels alphabetical."""
    item = create("items", item_body(labels=["alpha"]))

    updated = client.patch(
        f"{trip_url}/items/{item['id']}", json={"labels": ["yankee", "bravo"]}
    ).json()["item"]

    assert updated["labels"] == ["bravo", "yankee"]


def test_item_labels_are_alphabetical_on_read(client, trip_url, item_body, create):
    """Reading an item back answers with its labels alphabetical."""
    item = create("items", item_body(labels=["zulu", "alpha", "mike"]))

    read_back = client.get(f"{trip_url}/items/{item['id']}").json()["item"]

    assert read_back["labels"] == ["alpha", "mike", "zulu"]


def test_create_label_starts_unused(client, trip_url):
    """A label created directly exists with use_count 0, attached to nothing."""
    response = client.post(f"{trip_url}/labels", json={"name": "street-food"})

    assert response.status_code == 201, response.text
    label = response.json()["label"]
    assert label["name"] == "street-food"
    assert label["use_count"] == 0


def test_create_label_that_normalizes_onto_an_existing_one_is_409(
    client, trip_url, item_body, create
):
    """A label whose normalized form is already taken conflicts, whatever its casing."""
    create("items", item_body(labels=["food"]))

    response = client.post(f"{trip_url}/labels", json={"name": "Food"})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {"name": {"code": "duplicate", "params": {"name": "Food"}}},
        }
    }


def test_rename_label_keeps_it_attached_to_its_items(client, trip_url, item_body, create):
    """A renamed label keeps its use count and the items already carrying it."""
    item = create("items", item_body(labels=["food"]))
    label_id = client.get(f"{trip_url}/labels").json()["labels"][0]["id"]

    response = client.patch(f"{trip_url}/labels/{label_id}", json={"name": "dining"})

    assert response.status_code == 200
    assert response.json()["label"]["name"] == "dining"
    assert response.json()["label"]["use_count"] == 1
    read_back = client.get(f"{trip_url}/items/{item['id']}").json()["item"]
    assert read_back["labels"] == ["dining"]


def test_rename_label_onto_another_label_is_409(client, item_body, trip_url, create):
    """Renaming a label onto a name the trip already holds conflicts."""
    create("items", item_body(labels=["food", "fun"]))
    labels = client.get(f"{trip_url}/labels").json()["labels"]
    food = next(label for label in labels if label["name"] == "food")

    response = client.patch(f"{trip_url}/labels/{food['id']}", json={"name": "fun"})

    assert response.status_code == 409
    assert response.json()["error"]["fields"]["name"] == {
        "code": "duplicate",
        "params": {"name": "fun"},
    }


def test_patch_label_without_a_name_leaves_it_alone(client, trip_url, create):
    """A PATCH carrying no name is accepted and changes nothing."""
    label = create("labels", {"name": "food"})

    response = client.patch(f"{trip_url}/labels/{label['id']}", json={})

    assert response.status_code == 200
    assert response.json()["label"] == label


def test_one_item_carrying_a_label_twice_counts_it_once(client, trip_url, item_body, create):
    """Two tokens that normalize the same on one item make one label used once."""
    item = create("items", item_body(labels=["food", "Food"]))

    labels = client.get(f"{trip_url}/labels").json()["labels"]
    assert item["labels"] == ["food"]
    assert [(label["name"], label["use_count"]) for label in labels] == [("food", 1)]


def test_relabelling_an_item_moves_only_the_labels_that_changed(
    client, trip_url, item_body, create
):
    """Re-labelling deletes what left unused, adds what arrived and keeps what stayed."""
    item = create("items", item_body(labels=["alpha", "bravo"]))

    client.patch(f"{trip_url}/items/{item['id']}", json={"labels": ["bravo", "charlie"]})

    labels = client.get(f"{trip_url}/labels").json()["labels"]
    assert {label["name"]: label["use_count"] for label in labels} == {
        "bravo": 1,
        "charlie": 1,
    }


def test_item_echoes_the_label_name_as_stored(item_body, create):
    """An item's labels carry the stored casing, not the matching form, however it was re-typed."""
    first = create("items", item_body(labels=["Food"]))
    second = create("items", item_body(labels=["food"]))

    assert first["labels"] == ["Food"]
    assert second["labels"] == ["Food"]


def test_rename_label_changing_only_its_casing_is_allowed(client, trip_url, item_body, create):
    """A label can be recased in place without conflicting with itself; items show the new name."""
    item = create("items", item_body(labels=["food"]))
    label_id = client.get(f"{trip_url}/labels").json()["labels"][0]["id"]

    response = client.patch(f"{trip_url}/labels/{label_id}", json={"name": "Food"})

    assert response.status_code == 200
    assert response.json()["label"]["name"] == "Food"
    read_back = client.get(f"{trip_url}/items/{item['id']}").json()["item"]
    assert read_back["labels"] == ["Food"]
