import os
from itertools import cycle
from dotenv import load_dotenv

load_dotenv()

# Counters for tracking API keys and groq_models
total_keys = 0
total_models = 0
rotation_count = 0

# Dictionary to track API key usage per model
model_key_usage = {}

# Load keys
groq_api_keys = os.getenv("GROQ_API_KEYS", "").split(",")
if groq_api_keys[0] == "":
    raise ValueError("❌ No GROQ_API_KEYS found in .env file")
else:
    groq_api_keys = [k.strip() for k in groq_api_keys if k.strip()]
    total_keys = len(groq_api_keys)
    print(f"✅ [DEBUG] {total_keys} GROQ_API_KEYS found in .env file")

if not groq_api_keys:
    raise ValueError("❌ No GROQ_API_KEYS found in .env file")

# Load groq_models
groq_models = os.getenv("GROQ_MODELS", "").split(",")
if groq_models[0] == "":
    raise ValueError("❌ No GROQ_MODELS found in .env file")
else:
    groq_models = [m.strip() for m in groq_models if m.strip()]
    total_models = len(groq_models)
    print(f"✅ [DEBUG] {total_models} GROQ_MODELS found in .env file: {groq_models}")

if not groq_models:
    groq_models = ["llama-3.1-8b-instant"]
    total_models = 1

available_groq_keys = groq_api_keys.copy()
available_groq_models = groq_models.copy()

key_cycle = cycle(available_groq_keys)
model_cycle = cycle(available_groq_models)

current_groq_key = next(key_cycle)
current_groq_model = next(model_cycle)

# Initialize counters
keys_remaining = len(available_groq_keys)
models_remaining = len(available_groq_models)
rotation_count = 0

# Initialize model_key_usage dictionary
for model in groq_models:
    model_key_usage[model] = {
        "total_keys": len(groq_api_keys),
        "keys_used": 0,
        "rotations": 0
    }

def get_current_key():
    return current_groq_key

def get_current_model():
    return current_groq_model

def get_all_models():
    return groq_models

def set_current_model(model_name):
    global current_groq_model, model_cycle
    if model_name not in groq_models:
        raise ValueError(f"Model '{model_name}' not found in available groq_models.")
    current_groq_model = model_name
    # Reset the model_cycle to start from the newly set current_groq_model
    # This is a simplified approach; a more robust solution might re-create the cycle
    # to ensure all groq_models are still eventually rotated through if needed.
    model_cycle = cycle([current_groq_model] + [m for m in available_groq_models if m != current_groq_model])

def get_rotation_stats():
    """Get statistics about API key and model rotation."""
    return {
        "total_keys": total_keys,
        "keys_remaining": keys_remaining,
        "total_models": total_models,
        "models_remaining": models_remaining,
        "rotation_count": rotation_count,
        "current_groq_model": current_groq_model,
        "current_key_prefix": current_groq_key[:8] if current_groq_key else None,
        "model_key_usage": model_key_usage
    }

def print_rotation_status():
    """Print the current rotation status for debugging."""
    stats = get_rotation_stats()
    print(f"📊 [ROTATION STATUS] Rotation #{stats['rotation_count']}")
    print(f"   - Current model: {stats['current_groq_model']} ({stats['models_remaining']}/{stats['total_models']} groq_models remaining)")
    print(f"   - Current key: {stats['current_key_prefix']}... ({stats['keys_remaining']}/{stats['total_keys']} keys remaining)")
    
    # Print model-specific key usage if available
    if hasattr(rotate_key, 'model_keys'):
        print("\n📊 [MODEL-SPECIFIC KEY AVAILABILITY]")
        for model, keys in rotate_key.model_keys.items():
            is_current = model == current_groq_model
            print(f"   - {model}{' (current)' if is_current else ''}: {len(keys)}/{total_keys} keys available")
    
    return stats

def reset_rotation_counters():
    """Reset all rotation counters and restore all keys and groq_models."""
    global available_groq_keys, available_groq_models, key_cycle, model_cycle, current_groq_key, current_groq_model, keys_remaining, models_remaining, rotation_count, model_key_usage
    
    # Reset available keys and groq_models
    available_groq_keys = groq_api_keys.copy()
    available_groq_models = groq_models.copy()
    
    # Reset cycles
    key_cycle = cycle(available_groq_keys)
    model_cycle = cycle(available_groq_models)
    
    # Reset current key and model
    current_groq_key = next(key_cycle)
    current_groq_model = next(model_cycle)
    
    # Reset counters
    keys_remaining = len(available_groq_keys)
    models_remaining = len(available_groq_models)
    rotation_count = 0
    
    # Reset model_key_usage
    for model in groq_models:
        model_key_usage[model] = {
            "total_keys": len(groq_api_keys),
            "keys_used": 0,
            "rotations": 0
        }
    
    # Reset the model_keys tracking in rotate_key function
    if hasattr(rotate_key, 'model_keys'):
        delattr(rotate_key, 'model_keys')
    
    print("🔄 [DEBUG] Rotation counters reset. All keys and groq_models restored.")
    print_rotation_status()
    return True

def rotate_key():
    """Switch to next API key. If none left for this model, rotate model."""
    global current_groq_key, available_groq_keys, key_cycle, keys_remaining, rotation_count, model_key_usage

    rotation_count += 1
    exhausted = current_groq_key
    
    # Instead of removing the key globally, track it per model
    # Create a model-specific key list if it doesn't exist
    if not hasattr(rotate_key, 'model_keys'):
        rotate_key.model_keys = {}
    
    # Initialize model-specific key list if needed
    if current_groq_model not in rotate_key.model_keys:
        rotate_key.model_keys[current_groq_model] = groq_api_keys.copy()
    
    # Remove the exhausted key from this model's available keys
    if exhausted in rotate_key.model_keys[current_groq_model]:
        rotate_key.model_keys[current_groq_model] = [k for k in rotate_key.model_keys[current_groq_model] if k != exhausted]
    
    # Update the global available_groq_keys to be the current model's available keys
    available_groq_keys = rotate_key.model_keys[current_groq_model]
    keys_remaining = len(available_groq_keys)
    
    # Update model_key_usage
    model_key_usage[current_groq_model]["keys_used"] += 1
    model_key_usage[current_groq_model]["rotations"] += 1

    if not available_groq_keys:
        print(f"⚠️ [DEBUG] All API keys exhausted for model {current_groq_model}. Rotating to next model.")
        print(f"📊 [STATS] Rotation #{rotation_count}: No keys left for {current_groq_model}, switching groq_models")
        return rotate_model()

    key_cycle = cycle(available_groq_keys)
    current_groq_key = next(key_cycle)

    print(f"🔑 [DEBUG] API key switched for model {current_groq_model}: {exhausted[:8]}... ➝ {current_groq_key[:8]}... ({keys_remaining}/{total_keys} keys remaining)")
    print(f"📊 [STATS] Rotation #{rotation_count}: {keys_remaining}/{total_keys} keys and {models_remaining}/{total_models} groq_models available")
    return current_groq_key


def rotate_model():
    """Switch to next model and reset API keys."""
    global current_groq_model, available_groq_models, model_cycle, available_groq_keys, key_cycle, current_groq_key, models_remaining, keys_remaining, rotation_count, model_key_usage

    rotation_count += 1
    exhausted = current_groq_model
    available_groq_models = [m for m in available_groq_models if m != exhausted]
    models_remaining = len(available_groq_models)
    
    # Update model_key_usage for the exhausted model
    model_key_usage[exhausted]["keys_used"] = total_keys  # All keys used for this model

    if not available_groq_models:
        print(f"❌ [CRITICAL] All groq_models exhausted: {groq_models}")
        print(f"📊 [STATS] Final rotation #{rotation_count}: All {total_models} groq_models exhausted after trying all {total_keys} keys")
        raise RuntimeError(f"❌ All groq_models exhausted: {groq_models}")

    model_cycle = cycle(available_groq_models)
    current_groq_model = next(model_cycle)

    # Check if we've already used this model before
    if hasattr(rotate_key, 'model_keys') and current_groq_model in rotate_key.model_keys:
        # Use the existing key list for this model
        available_groq_keys = rotate_key.model_keys[current_groq_model]
    else:
        # Reset API keys for new model
        available_groq_keys = groq_api_keys.copy()
        # Initialize in the model_keys dictionary if it exists
        if hasattr(rotate_key, 'model_keys'):
            rotate_key.model_keys[current_groq_model] = groq_api_keys.copy()
    
    keys_remaining = len(available_groq_keys)
    key_cycle = cycle(available_groq_keys)
    current_groq_key = next(key_cycle)

    print(f"🔄 [DEBUG] Model switched: {exhausted} ➝ {current_groq_model} with {keys_remaining} fresh API keys")
    print(f"📊 [STATS] Rotation #{rotation_count}: Switched to model {current_groq_model}, reset to {keys_remaining}/{total_keys} keys, {models_remaining}/{total_models} groq_models remaining")
    return current_groq_model
