import os
from itertools import cycle
from dotenv import load_dotenv

load_dotenv()

# Counters for tracking API keys and models
total_keys = 0
total_models = 0
rotation_count = 0

# Dictionary to track API key usage per model
model_key_usage = {}

# Load keys
api_keys = os.getenv("GROQ_API_KEYS", "").split(",")
if api_keys[0] == "":
    raise ValueError("❌ No GROQ_API_KEYS found in .env file")
else:
    api_keys = [k.strip() for k in api_keys if k.strip()]
    total_keys = len(api_keys)
    print(f"✅ [DEBUG] {total_keys} GROQ_API_KEYS found in .env file")

if not api_keys:
    raise ValueError("❌ No GROQ_API_KEYS found in .env file")

# Load models
models = os.getenv("GROQ_MODELS", "").split(",")
if models[0] == "":
    raise ValueError("❌ No GROQ_MODELS found in .env file")
else:
    models = [m.strip() for m in models if m.strip()]
    total_models = len(models)
    print(f"✅ [DEBUG] {total_models} GROQ_MODELS found in .env file: {models}")

if not models:
    models = ["llama-3.1-8b-instant"]
    total_models = 1

available_keys = api_keys.copy()
available_models = models.copy()

key_cycle = cycle(available_keys)
model_cycle = cycle(available_models)

current_key = next(key_cycle)
current_model = next(model_cycle)

# Initialize counters
keys_remaining = len(available_keys)
models_remaining = len(available_models)
rotation_count = 0

# Initialize model_key_usage dictionary
for model in models:
    model_key_usage[model] = {
        "total_keys": len(api_keys),
        "keys_used": 0,
        "rotations": 0
    }

def get_current_key():
    return current_key

def get_current_model():
    return current_model

def get_rotation_stats():
    """Get statistics about API key and model rotation."""
    return {
        "total_keys": total_keys,
        "keys_remaining": keys_remaining,
        "total_models": total_models,
        "models_remaining": models_remaining,
        "rotation_count": rotation_count,
        "current_model": current_model,
        "current_key_prefix": current_key[:8] if current_key else None,
        "model_key_usage": model_key_usage
    }

def print_rotation_status():
    """Print the current rotation status for debugging."""
    stats = get_rotation_stats()
    print(f"📊 [ROTATION STATUS] Rotation #{stats['rotation_count']}")
    print(f"   - Current model: {stats['current_model']} ({stats['models_remaining']}/{stats['total_models']} models remaining)")
    print(f"   - Current key: {stats['current_key_prefix']}... ({stats['keys_remaining']}/{stats['total_keys']} keys remaining)")
    
    # Print model-specific key usage if available
    if hasattr(rotate_key, 'model_keys'):
        print("\n📊 [MODEL-SPECIFIC KEY AVAILABILITY]")
        for model, keys in rotate_key.model_keys.items():
            is_current = model == current_model
            print(f"   - {model}{' (current)' if is_current else ''}: {len(keys)}/{total_keys} keys available")
    
    return stats

def reset_rotation_counters():
    """Reset all rotation counters and restore all keys and models."""
    global available_keys, available_models, key_cycle, model_cycle, current_key, current_model, keys_remaining, models_remaining, rotation_count, model_key_usage
    
    # Reset available keys and models
    available_keys = api_keys.copy()
    available_models = models.copy()
    
    # Reset cycles
    key_cycle = cycle(available_keys)
    model_cycle = cycle(available_models)
    
    # Reset current key and model
    current_key = next(key_cycle)
    current_model = next(model_cycle)
    
    # Reset counters
    keys_remaining = len(available_keys)
    models_remaining = len(available_models)
    rotation_count = 0
    
    # Reset model_key_usage
    for model in models:
        model_key_usage[model] = {
            "total_keys": len(api_keys),
            "keys_used": 0,
            "rotations": 0
        }
    
    # Reset the model_keys tracking in rotate_key function
    if hasattr(rotate_key, 'model_keys'):
        delattr(rotate_key, 'model_keys')
    
    print("🔄 [DEBUG] Rotation counters reset. All keys and models restored.")
    print_rotation_status()
    return True

def rotate_key():
    """Switch to next API key. If none left for this model, rotate model."""
    global current_key, available_keys, key_cycle, keys_remaining, rotation_count, model_key_usage

    rotation_count += 1
    exhausted = current_key
    
    # Instead of removing the key globally, track it per model
    # Create a model-specific key list if it doesn't exist
    if not hasattr(rotate_key, 'model_keys'):
        rotate_key.model_keys = {}
    
    # Initialize model-specific key list if needed
    if current_model not in rotate_key.model_keys:
        rotate_key.model_keys[current_model] = api_keys.copy()
    
    # Remove the exhausted key from this model's available keys
    if exhausted in rotate_key.model_keys[current_model]:
        rotate_key.model_keys[current_model] = [k for k in rotate_key.model_keys[current_model] if k != exhausted]
    
    # Update the global available_keys to be the current model's available keys
    available_keys = rotate_key.model_keys[current_model]
    keys_remaining = len(available_keys)
    
    # Update model_key_usage
    model_key_usage[current_model]["keys_used"] += 1
    model_key_usage[current_model]["rotations"] += 1

    if not available_keys:
        print(f"⚠️ [DEBUG] All API keys exhausted for model {current_model}. Rotating to next model.")
        print(f"📊 [STATS] Rotation #{rotation_count}: No keys left for {current_model}, switching models")
        return rotate_model()

    key_cycle = cycle(available_keys)
    current_key = next(key_cycle)

    print(f"🔑 [DEBUG] API key switched for model {current_model}: {exhausted[:8]}... ➝ {current_key[:8]}... ({keys_remaining}/{total_keys} keys remaining)")
    print(f"📊 [STATS] Rotation #{rotation_count}: {keys_remaining}/{total_keys} keys and {models_remaining}/{total_models} models available")
    return current_key


def rotate_model():
    """Switch to next model and reset API keys."""
    global current_model, available_models, model_cycle, available_keys, key_cycle, current_key, models_remaining, keys_remaining, rotation_count, model_key_usage

    rotation_count += 1
    exhausted = current_model
    available_models = [m for m in available_models if m != exhausted]
    models_remaining = len(available_models)
    
    # Update model_key_usage for the exhausted model
    model_key_usage[exhausted]["keys_used"] = total_keys  # All keys used for this model

    if not available_models:
        print(f"❌ [CRITICAL] All models exhausted: {models}")
        print(f"📊 [STATS] Final rotation #{rotation_count}: All {total_models} models exhausted after trying all {total_keys} keys")
        raise RuntimeError(f"❌ All models exhausted: {models}")

    model_cycle = cycle(available_models)
    current_model = next(model_cycle)

    # Check if we've already used this model before
    if hasattr(rotate_key, 'model_keys') and current_model in rotate_key.model_keys:
        # Use the existing key list for this model
        available_keys = rotate_key.model_keys[current_model]
    else:
        # Reset API keys for new model
        available_keys = api_keys.copy()
        # Initialize in the model_keys dictionary if it exists
        if hasattr(rotate_key, 'model_keys'):
            rotate_key.model_keys[current_model] = api_keys.copy()
    
    keys_remaining = len(available_keys)
    key_cycle = cycle(available_keys)
    current_key = next(key_cycle)

    print(f"🔄 [DEBUG] Model switched: {exhausted} ➝ {current_model} with {keys_remaining} fresh API keys")
    print(f"📊 [STATS] Rotation #{rotation_count}: Switched to model {current_model}, reset to {keys_remaining}/{total_keys} keys, {models_remaining}/{total_models} models remaining")
    return current_model
