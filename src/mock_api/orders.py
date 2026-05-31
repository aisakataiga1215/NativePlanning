import uuid
from src.schemas.order import ExecutionResult
from src.mock_api.restaurants import get_coupon


def purchase_coupon(coupon_id: str, quantity: int) -> ExecutionResult:
    coupon = get_coupon(coupon_id)
    if not coupon:
        return ExecutionResult(
            action_type="purchase_coupon",
            status="failed",
            message="优惠券不存在",
            error_reason="coupon_not_found",
        )
    if not coupon.available:
        return ExecutionResult(
            action_type="purchase_coupon",
            status="failed",
            message=f"优惠券「{coupon.title}」已售完",
            error_reason="coupon_unavailable",
        )
    order_id = f"cpn_{uuid.uuid4().hex[:8]}"
    total = coupon.price * quantity
    return ExecutionResult(
        action_type="purchase_coupon",
        status="success",
        order_id=order_id,
        message=f"已购买「{coupon.title}」× {quantity}，共 ¥{total:.0f}",
    )


def order_addon(
    addon_type: str,
    near_location: str,
    date: str,
    time: str,
    quantity: int,
) -> ExecutionResult:
    _ADDON_NAMES = {
        "drink": "饮品",
        "cake": "蛋糕",
        "flowers": "鲜花",
        "snack": "小食",
    }
    name = _ADDON_NAMES.get(addon_type, addon_type)
    order_id = f"addon_{uuid.uuid4().hex[:8]}"
    return ExecutionResult(
        action_type="order_addon",
        status="success",
        order_id=order_id,
        message=f"已安排 {name} × {quantity} 在 {time} 送达",
    )
