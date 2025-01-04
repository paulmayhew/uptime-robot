# Uptime Robot

Uptime Robot is a simple uptime monitoring service that pings your website at regular intervals and notifies you if it ever goes down. It's a great way to keep an eye on your website and make sure it's always up and running.

I started this project due to the frustration of downtime of original [uptime&nbsp;robot](https://uptimerobot.com/) service. I wanted to have a simple uptime monitoring service that I could run on my own AWS server and have control over. The setup and configuration of this project are easy enough to tailor to your needs.

## Features

- **Simple**: Uptime Robot is designed to be simple and easy to use. Just add your website URL and email address, and you're good to go.

- **Customizable**: You can customize the monitoring interval, timeout, and notification settings to suit your needs.

- **Self-hosted**: Uptime Robot is a self-hosted solution, so you have full control over your data and can run it on your own server.

- **Open-source**: Uptime Robot is open-source and free to use. You can view the source code on [GitHub](https://github.com/J16N/uptime-robot).

## Getting Started

To get started with Uptime Robot, follow these steps:

1. Clone the repository.

    ```bash
    git clone https://github.com/J16N/uptime-robot.git
    ```

2. Install the dependencies.

    ```bash
    cd uptime-robot
    poetry shell
    poetry install
    ```

3. Create a `.env` file and add your configuration. You can use the `.env.example` file as a template.

    ```bash
    cp .env.example .env
    ```

4. Run the application. It will generate `monitor.txt` file. Add the links you want to monitor in this file. Each link should be on a new line.

    ```bash
    python main.py
    ```


## Configuration

You can configure Uptime Robot by editing the `.env` file. Here are the available options:

- `MAIL_FROM`: The email address to send notifications from.
- `MONITOR_INTERVAL`: The monitoring interval in seconds. Default is `60`.
- `NAME`: The name of the user. This is used in the email notifications. Default is `User`.
- `REQUEST_RETRIES`: The number of request retries. Default is `10`.
- `REQUEST_TIMEOUT`: The request timeout in seconds. Default is `10`.
- `RECIPIENTS`: The email addresses to send notifications to.
- `SEND_EMAIL_RETRIES`: The number of retries to make if email send fails. Default is `10`.
- `SMTP_HOST`: The SMTP server to use for sending emails. Default is `smtp.gmail.com`.
- `SMTP_PORT`: The SMTP server port to use for sending emails. Default is `465`.
- `SMTP_USERNAME`: The SMTP server username to use for sending emails.
- `SMTP_PASSWORD`: The SMTP server password to use for sending emails.