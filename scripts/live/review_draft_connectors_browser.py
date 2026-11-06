"""Actual disposable desktop/mobile Drafts path; no provider or send calls."""
import httpx
from playwright.sync_api import expect
import review_agent_team_browser as runner


def verify(page, width):
    with httpx.Client(base_url=runner.BASE, headers={'Authorization': 'Bearer ' + runner.TOKEN}) as client:
        campaigns = client.get('/api/v1/campaigns').json()['items']
        campaign = next(row for row in campaigns if row['name'] == 'QA email')['id']
        response = client.post(f'/api/v1/campaigns/{campaign}/contacts/import', files={'file': (
            'contacts.csv', b'Full Name,Email,Company,Category\nAnita Rao,anita@example.com,Example Exports,CBAM\n', 'text/csv')})
        assert response.status_code == 200, response.text
    page.add_init_script("localStorage.setItem('offsetx-active-campaign', " + __import__('json').dumps(campaign) + ")")
    page.goto(runner.BASE + '/#drafts', wait_until='domcontentloaded')
    page.get_by_role('heading', name='Draft review', exact=True).wait_for()
    page.get_by_role('button', name='Generate sequence', exact=True).first.click()
    mode = page.get_by_label('Generation mode', exact=True)
    expect(mode).to_have_value('local')
    expect(mode.locator('option[value="connectors"]')).to_have_attribute('disabled', '')
    expect(page.get_by_role('link', name='Open Connectors', exact=True)).to_have_attribute('href', '#connectors')
    with page.expect_response(lambda response: '/drafts/generate' in response.url) as generated:
        page.get_by_role('button', name='Generate drafts', exact=True).click()
    assert generated.value.status == 200, generated.value.text()
    assert generated.value.json()['generated'] == 3
    expect(page.get_by_role('heading', name='Generate three-stage sequence', exact=True)).to_have_count(0)
    expect(page.get_by_text('Template', exact=True).first).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(runner.ROOT / 'work/three-features' / f'drafts-connectors-{width}.png'))
    print(f'PASS Drafts {width}px: local templates, Connectors setup action, unavailable-provider gate, actual generation and mandatory review', flush=True)


if __name__ == '__main__':
    runner.verify = verify
    runner.main()
