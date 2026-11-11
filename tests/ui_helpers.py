from tests.test_net_integration import wait_until


async def click_button(pilot, selector):
    """Wait for asynchronously mounted rows to receive real screen coordinates."""
    def laid_out():
        nodes = pilot.app.screen.query(selector)
        return bool(nodes) and nodes.first().region.width > 0 and nodes.first().region.height > 0
    await wait_until(laid_out)
    await pilot.pause(.05)
    button = pilot.app.screen.query_one(selector)
    assert await pilot.click(selector, offset=(min(2, button.region.width-1), min(1, button.region.height-1)))
    return True
