import asyncio, uuid

SESSIONS = {
    "tony": "01a13957-54c2-74cf-8377-06bcab8df6ea",
    "friday": "01a13957-9105-7495-a49c-14040fefd5b6",
    "jarvis": "01a13957-a086-7aee-ad4a-5ad834756dfa",
}

_queue = None
_futures = {}

def queue():
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue

async def ask_arena(agent_id, text, timeout=240):
    job_id = str(uuid.uuid4())
    future = asyncio.get_running_loop().create_future()
    _futures[job_id] = future
    await queue().put({
        "id": job_id,
        "sessionId": SESSIONS[agent_id],
        "text": text,
    })
    try:
        return await asyncio.wait_for(future, timeout)
    except asyncio.TimeoutError as exc:
        raise RuntimeError(f"{agent_id} did not reply on Arena in time") from exc
    finally:
        _futures.pop(job_id, None)

def take_job():
    if _queue is None or _queue.empty():
        return {"id": None}
    return _queue.get_nowait()

def complete_job(job_id, reply=None, error=None):
    future = _futures.get(job_id)
    if future is None or future.done():
        return False
    if error:
        future.set_exception(RuntimeError(error))
    else:
        future.set_result(reply or "")
    return True

def channel_prompt(name, sender, content):
    return (
        f"Group channel message from {sender} to {name}:\n{content}\n\n"
        "Reply in this same channel. Mention teammates as @friday, @jarvis, or @tony only — never full bot usernames. "
        "When the message asks you to review, audit, or find bugs, use read-only tools and report what you actually see. "
        "Do not edit files unless the message asks you to change the repo."
    )
