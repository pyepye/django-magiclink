from django.urls import reverse


def test_login_page(client):
    url = reverse('magiclink:login')
    response = client.get(url)
    assert response.context_data['login_form']
    assert response.status_code == 200
