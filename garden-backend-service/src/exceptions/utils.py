import re
import traceback


def format_traceback(exc: Exception, func_to_stop_at: str = "run_endpoint_function"):
    """Filter the stack trace to include only the relevant part from the endpoint call to the error."""
    tb = traceback.extract_tb(exc.__traceback__)  # Extract the stack frames

    # Find the frame for the most recent endpoint call
    relevant_frames = []

    for frame in reversed(tb):  # Walk the stack from the bottom (most recent call)
        filename, lineno, funcname, text = frame

        # stop when we hit the inital call to the endpoint
        if funcname == func_to_stop_at:
            break

        relevant_frames.append(frame)

    # If we found relevant frames, remove the noisy stuff
    if relevant_frames:
        filtered_tb = traceback.format_list(
            reversed(relevant_frames)
        )  # Reverse to maintain original order
        cleaned_tb = [re.sub(r"(\^+)", "", line).strip() for line in filtered_tb]
        return "".join(cleaned_tb)

    # Fallback to the full traceback if no endpoint call was found
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
