import requests
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

API = "http://127.0.0.1:8000"  # adresse du backend FastAPI


def api(method, path, **kwargs):
    """Appelle le backend. Retourne le JSON, ou None en cas d'erreur."""
    try:
        r = requests.request(method, API + path, timeout=5, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print("Erreur API :", e)
        return None


class ScrollList(ScrollView):
    """Une liste verticale défilable."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(5))
        self.box.bind(minimum_height=self.box.setter("height"))
        self.add_widget(self.box)


def make_button(text, callback, **kwargs):
    btn = Button(text=text, **kwargs)
    btn.bind(on_release=lambda *_: callback())
    return btn


# =====================  Écran principal  =====================
class StudentsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session_active = False  # True après avoir cliqué sur "Démarrer"
        self.pending_present_ids = set()

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(
            Label(text="Gestion de présence", font_size="22sp", size_hint_y=None, height=dp(40))
        )

        # Barre d'ajout d'un étudiant
        add_bar = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        self.name_input = TextInput(hint_text="Nom de l'étudiant", multiline=False)
        self.name_input.bind(on_text_validate=lambda *_: self.add_student())
        add_bar.add_widget(self.name_input)
        add_bar.add_widget(make_button("Ajouter", self.add_student, size_hint_x=None, width=dp(100)))
        root.add_widget(add_bar)

        self.info = Label(size_hint_y=None, height=dp(25))
        root.add_widget(self.info)

        self.list = ScrollList()
        root.add_widget(self.list)

        # Boutons du bas
        actions = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        actions.add_widget(make_button("Démarrer la présence", self.start_attendance))
        actions.add_widget(make_button("Présents", lambda: self.go("present")))
        actions.add_widget(make_button("Absents", lambda: self.go("absent")))
        root.add_widget(actions)

        self.add_widget(root)

    def on_pre_enter(self, *args):
        self.refresh()

    def go(self, screen_name):
        self.manager.current = screen_name

    # ----- Actions -----
    def add_student(self):
        name = self.name_input.text.strip()
        if name:
            api("POST", "/students", json={"name": name})
            self.name_input.text = ""
            self.refresh()

    def delete_student(self, student_id):
        api("DELETE", f"/students/{student_id}")
        self.pending_present_ids.discard(student_id)
        self.refresh()

    def start_attendance(self):
        result = api(
            "POST",
            "/attendance/start",
            json={"present_student_ids": sorted(self.pending_present_ids)},
        )
        if result is None:
            self.info.text = "Impossible de démarrer la présence. Vérifiez le serveur."
            return

        self.session_active = True
        self.pending_present_ids.clear()
        self.refresh()

    def toggle(self, student_id, is_present):
        if not self.session_active:
            if is_present:
                self.pending_present_ids.add(student_id)
            else:
                self.pending_present_ids.discard(student_id)
            return

        if api(
            "PUT",
            f"/students/{student_id}/presence",
            json={"present": is_present},
        ) is None:
            self.refresh()
            self.info.text = "Impossible d'enregistrer la présence. Vérifiez le serveur."

    # ----- Affichage -----
    def refresh(self):
        self.info.text = (
            "Présence en cours : cochez ou décochez les étudiants"
            if self.session_active
            else "Cochez les présents, puis démarrez la présence"
        )
        self.list.box.clear_widgets()
        students = api("GET", "/students")
        if students is None:
            self.info.text = "Impossible de joindre le serveur FastAPI !"
            return

        for s in students:
            row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
            cb = CheckBox(
                active=(
                    s["status"] == "present"
                    if self.session_active
                    else s["id"] in self.pending_present_ids
                ),
                size_hint_x=None,
                width=dp(40),
            )
            # sid=s["id"] "fige" l'id de cet étudiant pour cette ligne
            cb.bind(active=lambda inst, value, sid=s["id"]: self.toggle(sid, value))
            row.add_widget(cb)
            row.add_widget(Label(text=s["name"], halign="left"))
            row.add_widget(
                make_button(
                    "Supprimer",
                    lambda sid=s["id"]: self.delete_student(sid),
                    size_hint_x=None,
                    width=dp(100),
                )
            )
            self.list.box.add_widget(row)


# =====================  Écran Présents / Absents  =====================
class ListScreen(Screen):
    def __init__(self, kind, **kwargs):
        super().__init__(**kwargs)
        self.kind = kind  # "present" ou "absent"
        title = "Liste des présents" if kind == "present" else "Liste des absents"

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(Label(text=title, font_size="22sp", size_hint_y=None, height=dp(40)))
        self.list = ScrollList()
        root.add_widget(self.list)

        actions = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        actions.add_widget(make_button("Réinitialiser la liste", self.reset))
        actions.add_widget(make_button("Retour", lambda: setattr(self.manager, "current", "students")))
        root.add_widget(actions)
        self.add_widget(root)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.list.box.clear_widgets()
        students = api("GET", f"/attendance/{self.kind}")
        if students is None:
            self.list.box.add_widget(
                Label(
                    text="Impossible de joindre le serveur FastAPI !",
                    size_hint_y=None,
                    height=dp(40),
                )
            )
            return
        if not students:
            self.list.box.add_widget(Label(text="Aucun étudiant", size_hint_y=None, height=dp(40)))
        for s in students:
            self.list.box.add_widget(Label(text=s["name"], size_hint_y=None, height=dp(35)))

    def reset(self):
        api("POST", f"/attendance/{self.kind}/reset")
        self.refresh()


# =====================  Application  =====================
class PresenceApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(StudentsScreen(name="students"))
        sm.add_widget(ListScreen(kind="present", name="present"))
        sm.add_widget(ListScreen(kind="absent", name="absent"))
        return sm


if __name__ == "__main__":
    PresenceApp().run()