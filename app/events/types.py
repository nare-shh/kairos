from enum import StrEnum


class ProductEvent(StrEnum):
    """
    All events that can happen to a Product.

    Rules for naming events:
    1. Always past tense — events are facts, not commands
       ✓ ProductCreated    ✗ CreateProduct
       ✓ PriceChanged      ✗ ChangePrice
    2. Use the aggregate name as prefix — easier to filter by aggregate
    3. Be specific — "ProductPriceChanged" not "ProductUpdated"
       (future you will thank present you when debugging at 2am)
    """

    # Lifecycle events
    CREATED = "ProductCreated"
    ACTIVATED = "ProductActivated"
    DEACTIVATED = "ProductDeactivated"
    DELETED = "ProductDeleted"

    # Content events
    UPDATED = "ProductUpdated"
    IMAGE_UPLOADED = "ProductImageUploaded"
    STOCK_UPDATED = "ProductStockUpdated"

    # Pricing events — the core of Kairos novelty
    PRICE_CHANGED = "ProductPriceChanged"
    BASE_PRICE_SET = "ProductBasePriceSet"


class OrderEvent(StrEnum):
    """All events that can happen to an Order."""
    CREATED = "OrderCreated"
    CONFIRMED = "OrderConfirmed"
    PAYMENT_RECEIVED = "OrderPaymentReceived"
    SHIPPED = "OrderShipped"
    DELIVERED = "OrderDelivered"
    CANCELLED = "OrderCancelled"
    REFUNDED = "OrderRefunded"


class UserEvent(StrEnum):
    """All events that can happen to a User."""
    REGISTERED = "UserRegistered"
    LOGGED_IN = "UserLoggedIn"
    PROFILE_UPDATED = "UserProfileUpdated"
    DEACTIVATED = "UserDeactivated"


class IntentEvent(StrEnum):
    """
    Kairos-specific: User INTENT events.
    These are what feed the dynamic pricing engine.
    Every action a user takes on a product generates one of these.

    The pricing engine listens to these and adjusts prices in real-time.
    """
    PRODUCT_VIEWED = "ProductViewed"            # user opened product page
    PRODUCT_SEARCH = "ProductSearched"          # user searched for a product
    CART_ADDED = "CartAdded"                    # user added to cart
    CART_REMOVED = "CartRemoved"                # user removed from cart
    WISHLIST_ADDED = "WishlistAdded"            # saved for later
    CHECKOUT_STARTED = "CheckoutStarted"        # began checkout
    CHECKOUT_ABANDONED = "CheckoutAbandoned"    # started but didn't finish
    PURCHASE_COMPLETED = "PurchaseCompleted"    # actually bought
