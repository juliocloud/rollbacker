import docker
import time
import requests
import json
import os
import platform

CONTAINER_NAME = "my_app"
HEALTH_URL = "http://localhost:5000/health"
GOOD_IMAGES_FILE = "good_images.json"
CHECK_INTERVAL = 10 

system = platform.system()

if system == "Windows":
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        print("[!] Windows detected, switching to TCP connection on localhost:2375")
        client = docker.DockerClient(base_url='tcp://127.0.0.1:2375')
elif system == "Linux":
    client = docker.from_env()
else:
    raise EnvironmentError(f"Unsupported OS: {system}")

def load_good_images():
    if os.path.exists(GOOD_IMAGES_FILE):
        with open(GOOD_IMAGES_FILE) as f:
            return json.load(f)
    return {}

def save_good_image(container_name, image):
    data = load_good_images()
    data[container_name] = image
    with open(GOOD_IMAGES_FILE, "w") as f:
        json.dump(data, f)

def get_container(container_name):
    try:
        return client.containers.get(container_name)
    except docker.errors.NotFound:
        return None

def health_check():
    try:
        r = requests.get(HEALTH_URL, timeout=3)
        return r.status_code == 200
    except:
        return False

def rollback(container):
    good_images = load_good_images()
    last_good = good_images.get(CONTAINER_NAME)
    if not last_good:
        print("[!] No good image recorded, cannot rollback.")
        return
    print(f"[!] Rolling back to {last_good}")
    container.stop()
    client.containers.run(
        last_good,
        name=CONTAINER_NAME,
        detach=True,
        ports={'5000/tcp': 5000},
        remove=True
    )

print(f"[i] Starting rollbacker on {system} for container '{CONTAINER_NAME}'")
while True:
    container = get_container(CONTAINER_NAME)
    if not container:
        print(f"[!] Container {CONTAINER_NAME} not found, waiting...")
        time.sleep(CHECK_INTERVAL)
        continue

    if health_check():
        print("[+] Container healthy, saving image as good.")
        if container.image.tags:
            save_good_image(CONTAINER_NAME, container.image.tags[0])
    else:
        print("[!] Container failed health check!")
        rollback(container)

    time.sleep(CHECK_INTERVAL)
