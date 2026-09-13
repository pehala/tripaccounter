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
