from django.urls import reverse


def test_signup_page(client):
    url = reverse('magiclink:signup')
    response = client.get(url)
    assert response.context_data['SignupForm']
    assert response.context_data['SignupFormEmailOnly']
    assert response.context_data['SignupFormWithUsername']
    assert response.context_data['SignupFormFull']
    assert response.status_code == 200
