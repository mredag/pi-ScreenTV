from werkzeug.security import generate_password_hash
import getpass

password = getpass.getpass("Lütfen oluşturmak istediğiniz şifreyi girin: ")
password_confirm = getpass.getpass("Şifreyi tekrar girin: ")

if password != password_confirm:
    print("Şifreler eşleşmiyor. İşlem iptal edildi.")
else:
    hashed_password = generate_password_hash(password)
    print("\nŞifreniz başarıyla oluşturuldu.")
    print("Lütfen aşağıdaki hash'i config.json dosyanıza kopyalayın:")
    print("---------------------------------------------------------")
    print(f'"{hashed_password}"')
    print("---------------------------------------------------------")
