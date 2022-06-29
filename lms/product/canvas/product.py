from lms.product.canvas._plugin.grouping import CanvasGroupingPlugin
from lms.product.product import PluginConfig, Product, Routes


class Canvas(Product):
    """A product for Canvas specific settings and tweaks."""

    family = Product.Family.CANVAS

    route = Routes(
        oauth2_authorize="canvas_api.oauth.authorize",
        oauth2_refresh="canvas_api.oauth.refresh",
    )

    plugin_config = PluginConfig(grouping_service=CanvasGroupingPlugin)
