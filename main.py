from smtp_client import smtp


GMAIL_SMTP_SERVICE = "64.233.166.108"
USER = "temporary2016gone"
PASS_PHRASE = ""
MAIL_ADDR = USER + "temporary2016gone@gmail.com"
RECIPIENTS = "tone@walkmail.ru"


def main():
    smtp_client = smtp.Smtp(GMAIL_SMTP_SERVICE)

    smtp_client.connect()

    smtp_client.ehlo()

    smtp_client.starttls()

    smtp_client.ehlo()

    smtp_client.authenticate_plain(USER, PASS_PHRASE)

    smtp_client.mail(MAIL_ADDR, body="8BITMIME")

    smtp_client.send_recipients(RECIPIENTS)

    smtp_client.initiate_data()

    smtp_client.send_body("\r\n" + "This is a test")

    smtp_client.end_data()

    smtp_client.quit_terminate()


if __name__ == "__main__":
    main()