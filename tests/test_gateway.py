from cartograph.gateway import get_model, print_usage
from cartograph.schemas import Route

router = get_model("router", form=Route)
print(router.invoke("Where is the safe_path function defined?"))
print_usage()