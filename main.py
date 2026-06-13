
# Flask : Classe principale, initialise l'app
# render_template : Charge et compile les templates Jinja2
# session : Stockage côté serveur des données utilisateur
# request : Accès aux données de la requête HTTP
# url_for : Génération dynamique des URLs
# redirect : Redirection HTTP vers une autre route

# On importe mongodb, os, bcrypt (chiffrement des mdps)
import pymongo, os, bcrypt, random
from dotenv import load_dotenv


# On import du framework flask :
# * la classe Flask
# * render_template fonction qui permet d'afficher un fichier HTML
from flask import Flask, render_template, session, request, url_for, redirect
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os







load_dotenv()
print(os.getenv('MONGO_CLUSTER_URI'))

mongo_cluster_uri = os.getenv('MONGO_CLUSTER_URI')
print({mongo_cluster_uri})
client = MongoClient(mongo_cluster_uri)
db = client["db"]
print(db.list_collection_names())

# On crée une variable qui stocke une instance de la classe Flask
app = Flask(__name__)

# On crée une clef de chiffrement -> obligatoire pour utiliser session => elle signe et chiffre les cookies
# On crée une valeur au hasard de 24 bits
app.secret_key = os.urandom(24)

@app.context_processor
def inject_user_context():
    return {
        "utilisateur": session.get("utilisateur"),
        "role": session.get("role")
    }


def build_comment_tree(comments):
    nodes = {}
    for comment in comments:
        comment_id = str(comment['_id'])
        nodes[comment_id] = {
            'id': comment_id,
            'annonce_id': comment.get('annonce_id'),
            'auteur': comment.get('auteur'),
            'contenu': comment.get('contenu'),
            'parent_id': comment.get('parent_id'),
            'date': comment.get('date'),
            'replies': []
        }

    roots = []
    for node in nodes.values():
        parent_id = node.get('parent_id')
        if parent_id and parent_id in nodes:
            nodes[parent_id]['replies'].append(node)
        else:
            roots.append(node)

    def set_depth(item, depth=0):
        item['depth'] = depth
        for reply in item['replies']:
            set_depth(reply, depth + 1)

    for root in roots:
        set_depth(root, 0)

    return roots


def delete_comment_tree(comment_id):
    all_ids = [comment_id]
    queue = [comment_id]

    while queue:
        current_id = queue.pop()
        children = db.comments.find({"parent_id": current_id})
        for child in children:
            child_id = str(child['_id'])
            all_ids.append(child_id)
            queue.append(child_id)

    object_ids = [ObjectId(cid) for cid in all_ids]
    db.comments.delete_many({"_id": {"$in": object_ids}})
    db.reports.delete_many({"type": "comment", "item_id": {"$in": all_ids}})

# Connexion database

client = MongoClient({mongo_cluster_uri})
db = client["db"]


# On crée un route de notre page d'accueil
@app.route('/')
def index():
    annonces = list(db.annonces.find().sort('_id', -1))
    return render_template('index.html', annonces=annonces, utilisateur=session.get('utilisateur'))


# On crée le route pour l'inscription de l'utilisateur
@app.route('/register', methods = ['GET', 'POST'] )
def register():
    # On vérifie si la méthode est POST pour traiter le formulaire reçu
    if request.method == "POST": 
    # on récupère la table "utilisateurs" de notre base de données 
        db_users = db.users
        # On vérifie que le nom d'utilisateur n'est pas existant
        if db_users.find_one({"nom":request.form['utilisateur']}):
           return render_template("register.html", erreur = "Ce nom d'utilisateur est déjà pris")
        else :
            # On ajoute l'utilisateur à bdd après avoir chiffiré son mdp, si les mots de passe fournis sont égaux
            if request.form['mot_de_passe'] == request.form['verif_mot_de_passe']:
                # On chiffre le mdp avec hashpw 
                # gensalt pour hacher le mdp
                mot_de_passe_chiffre = bcrypt.hashpw(
                    request.form['mot_de_passe'].encode('utf-8'),
                    bcrypt.gensalt()
                )
                db_users.insert_one({
                    "nom": request.form['utilisateur'],
                    "mdp": mot_de_passe_chiffre,
                    "role": "standard"})

                # On ajoute le cookie utilisateur de connexion
                session["utilisateur"] = request.form['utilisateur']
                session["role"] = "standard"
                return redirect(url_for('index'))
            else :
                # On affiche l'erreur les mdps sont différents
                return render_template("register.html", erreur = "Les mots de passe ne sont pas identiques")

    # Autrement si c'est GET on affiche la page
    else : 
        return render_template("register.html")

# On crée le route pour la connexion de l'utilisateur
@app.route('/login', methods = ['GET', 'POST'])
def login():
    # On vérifie si la méthode est POST pour traiter le formulaire reçu
    if request.method == "POST": 
    # on récupère la table "utilisateurs" de notre base de données 
        db_users = db.users
        # On vérifie que le nom d'utilisateur n'est pas existant
        user = db_users.find_one({"nom":request.form['utilisateur']})
        if user : 
            # On verifie avec la fonction checkpw si le mdp du formulaire correspond au mdp de la base de données
            if bcrypt.checkpw(request.form["mot_de_passe"].encode('utf-8'), user["mdp"]):
                # On ajoute le cookie utilisateur de connexion
                session["utilisateur"] = request.form['utilisateur']
                session["role"] = user.get("role", "standard")
                return redirect(url_for('index'))
        # Sinon on affiche l'erreur 
        return render_template("login.html", erreur = "Les identifiants ne sont pas reconnus")

    # Si c'est GET 
    else :
        # On affiche la page de connexion
        return render_template("login.html")

# On crée le route pour la déconnexion de l'utilisateur
@app.route("/logout")
def logout():
    # On supprime le cookie de connexion de notre dictionnaire session
    session.clear()
    return redirect(url_for("index"))

# On créer le route pour la publication d'une annonce


# On teste notre base de données
@app.route('/test')
def test():
    db_test = db.test
    test = db_test.find({})
    return render_template("test.html", test=test)

# On crée le route pour la publication d'une annonce
@app.route('/publier', methods = ['GET', 'POST'])
def publier():
    if session.get("utilisateur") is None:
        return redirect(url_for('login'))

    if request.method == "POST":
        db_annonces = db.annonces
        db_annonces.insert_one({
            "auteur": session["utilisateur"],
            "titre": request.form['titre'],
            "contenu": request.form['contenu'],
        })
        return redirect(url_for('index'))
    else :
        return render_template("publier.html", utilisateur=session.get("utilisateur"))


@app.route('/annonce/<annonce_id>')
def voir_annonce(annonce_id):
    annonce = None
    try:
        annonce = db.annonces.find_one({"_id": ObjectId(annonce_id)})
    except Exception:
        annonce = None

    if not annonce:
        return render_template('annonce.html', annonce=None, erreur='Article introuvable', utilisateur=session.get('utilisateur'))

    comments = list(db.comments.find({"annonce_id": str(annonce_id)}).sort('date', 1))
    comments_tree = build_comment_tree(comments)

    return render_template('annonce.html', annonce=annonce, utilisateur=session.get('utilisateur'), comments_tree=comments_tree)

@app.route('/annonce/<annonce_id>/comment', methods=['POST'])
def add_comment(annonce_id):
    if session.get('utilisateur') is None:
        return redirect(url_for('login'))

    contenu = request.form.get('contenu', '').strip()
    parent_id = request.form.get('parent_id') or None
    if contenu:
        db.comments.insert_one({
            "annonce_id": str(annonce_id),
            "auteur": session.get('utilisateur'),
            "contenu": contenu,
            "parent_id": parent_id,
            "date": datetime.utcnow(),
        })

    return redirect(url_for('voir_annonce', annonce_id=annonce_id) + '#comments')

@app.route('/report', methods=['POST'])
def report_item():
    if session.get('utilisateur') is None:
        return redirect(url_for('login'))

    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')
    item_title = request.form.get('item_title', '')
    item_author = request.form.get('item_author', '')
    annonce_id = request.form.get('annonce_id')
    reporter = session.get('utilisateur')

    if item_type not in ['post', 'comment'] or not item_id:
        return redirect(request.referrer or url_for('index'))

    query = {"type": item_type, "item_id": item_id}
    existing = db.reports.find_one(query)

    if existing:
        if reporter not in existing.get('reporters', []):
            db.reports.update_one(query, {"$inc": {"count": 1}, "$addToSet": {"reporters": reporter}})
    else:
        report_doc = {
            "type": item_type,
            "item_id": item_id,
            "item_title": item_title,
            "item_author": item_author,
            "annonce_id": annonce_id,
            "count": 1,
            "reporters": [reporter],
            "created_at": datetime.utcnow(),
        }
        db.reports.insert_one(report_doc)

    return redirect(request.referrer or url_for('index'))

@app.route('/annonce/<annonce_id>/supprimer', methods=['POST'])
def supprimer_annonce(annonce_id):
    if session.get('utilisateur') is None:
        return redirect(url_for('login'))

    annonce = None
    try:
        annonce = db.annonces.find_one({"_id": ObjectId(annonce_id)})
    except Exception:
        annonce = None

    if not annonce or annonce.get('auteur') != session.get('utilisateur'):
        return redirect(url_for('index'))

    db.annonces.delete_one({"_id": ObjectId(annonce_id)})
    db.comments.delete_many({"annonce_id": str(annonce_id)})
    db.reports.delete_many({"type": "post", "item_id": str(annonce_id)})
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    users_count = db.users.count_documents({})
    annonces_count = db.annonces.count_documents({})
    comments_count = db.comments.count_documents({})
    reports_count = db.reports.count_documents({})
    recent_reports = list(db.reports.find().sort('count', -1).limit(5))

    users = []
    for user in db.users.find().sort('nom', 1):
        users.append({
            '_id': user['_id'],
            'id': str(user['_id']),
            'nom': user.get('nom', 'Utilisateur'),
            'role': user.get('role', 'standard')
        })

    report_counts = {}
    for report in db.reports.find():
        report_counts[f"{report['type']}:{report['item_id']}"] = report.get('count', 1)

    categories = {}
    for post in db.annonces.find().sort('titre', 1):
        category = post.get('categorie', 'Général')
        categories.setdefault(category, []).append({
            'id': str(post['_id']),
            'titre': post.get('titre', 'Sans titre'),
            'auteur': post.get('auteur', ''),
            'reports': report_counts.get(f"post:{str(post['_id'])}", 0)
        })

    post_reports = []
    for report in db.reports.find({"type": "post"}).sort('count', -1):
        post_reports.append({
            'id': str(report['_id']),
            'item_id': report.get('item_id'),
            'item_title': report.get('item_title'),
            'annonce_id': report.get('annonce_id'),
            'count': report.get('count', 1)
        })

    comment_reports = []
    for report in db.reports.find({"type": "comment"}).sort('count', -1):
        comment_reports.append({
            'id': str(report['_id']),
            'item_id': report.get('item_id'),
            'item_title': report.get('item_title'),
            'annonce_id': report.get('annonce_id'),
            'count': report.get('count', 1)
        })

    return render_template(
        'admin.html',
        users_count=users_count,
        annonces_count=annonces_count,
        comments_count=comments_count,
        reports_count=reports_count,
        recent_reports=recent_reports,
        users_list=users,
        categories=categories,
        post_reports=post_reports,
        comment_reports=comment_reports
    )

@app.route('/admin/change-role', methods=['POST'])
def change_user_role():
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    user_id = request.form.get('user_id')
    new_role = request.form.get('role', 'standard')
    if new_role not in ['standard', 'admin']:
        new_role = 'standard'

    try:
        db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": new_role}})
    except Exception:
        pass

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<user_id>')
def admin_user_detail(user_id):
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None

    if not user:
        return redirect(url_for('admin_dashboard'))

    user_name = user.get('nom')
    annonces = list(db.annonces.find({"auteur": user_name}).sort('_id', -1))
    comments = list(db.comments.find({"auteur": user_name}).sort('_id', -1))
    reports_count = db.reports.count_documents({
        "$or": [
            {"item_author": user_name},
            {"item_title": {"$regex": user_name, "$options": "i"}}
        ]
    })

    return render_template(
        'admin_user.html',
        user={
            'id': str(user['_id']),
            'nom': user_name,
            'role': user.get('role', 'standard')
        },
        annonces=annonces,
        comments=comments,
        reports_count=reports_count
    )

@app.route('/admin/user/<user_id>/delete', methods=['POST'])
def delete_user(user_id):
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None

    if not user:
        return redirect(url_for('admin_dashboard'))

    user_name = user.get('nom')
    db.users.delete_one({"_id": ObjectId(user_id)})
    db.annonces.delete_many({"auteur": user_name})
    db.comments.delete_many({"auteur": user_name})
    db.reports.delete_many({
        "$or": [
            {"item_author": user_name},
            {"item_title": {"$regex": user_name, "$options": "i"}}
        ]
    })

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/post/<post_id>/delete', methods=['POST'])
def admin_delete_post(post_id):
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    try:
        post = db.annonces.find_one({"_id": ObjectId(post_id)})
    except Exception:
        post = None

    if post:
        db.annonces.delete_one({"_id": ObjectId(post_id)})
        db.comments.delete_many({"annonce_id": str(post_id)})
        db.reports.delete_many({"type": "post", "item_id": str(post_id)})

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/comment/<comment_id>/delete', methods=['POST'])
def admin_delete_comment(comment_id):
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    try:
        comment = db.comments.find_one({"_id": ObjectId(comment_id)})
    except Exception:
        comment = None

    if comment:
        delete_comment_tree(str(comment['_id']))

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/report/<item_type>/<item_id>')
def admin_report_detail(item_type, item_id):
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    if item_type not in ['post', 'comment']:
        return redirect(url_for('admin_dashboard'))

    report = db.reports.find_one({"type": item_type, "item_id": item_id})
    if not report:
        return redirect(url_for('admin_dashboard'))

    if item_type == 'post':
        try:
            post = db.annonces.find_one({"_id": ObjectId(item_id)})
        except Exception:
            post = None
        return render_template('admin_report_detail.html', report=report, post=post)

    try:
        comment = db.comments.find_one({"_id": ObjectId(item_id)})
    except Exception:
        comment = None

    annonce = None
    if comment and comment.get('annonce_id'):
        try:
            annonce = db.annonces.find_one({"_id": ObjectId(comment.get('annonce_id'))})
        except Exception:
            annonce = None

    return render_template('admin_report_detail.html', report=report, comment=comment, annonce=annonce)

@app.route('/annonce/<annonce_id>/comment/<comment_id>/delete', methods=['POST'])
def supprimer_commentaire(annonce_id, comment_id):
    if session.get('utilisateur') is None:
        return redirect(url_for('login'))

    try:
        comment = db.comments.find_one({"_id": ObjectId(comment_id)})
    except Exception:
        comment = None

    if not comment:
        return redirect(url_for('voir_annonce', annonce_id=annonce_id) + '#comments')

    if comment.get('auteur') != session.get('utilisateur') and session.get('role') != 'admin':
        return redirect(url_for('voir_annonce', annonce_id=annonce_id) + '#comments')

    delete_comment_tree(str(comment['_id']))
    return redirect(url_for('voir_annonce', annonce_id=annonce_id) + '#comments')

@app.route('/admin/report/ignore', methods=['POST'])
def admin_ignore_report():
    if session.get('utilisateur') is None or session.get('role') != 'admin':
        return redirect(url_for('index'))

    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')
    if item_type in ['post', 'comment'] and item_id:
        db.reports.delete_many({"type": item_type, "item_id": item_id})

    return redirect(url_for('admin_dashboard'))

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', utilisateur=session.get('utilisateur')), 404

# On exécute de notre application flask à laquelle on accède via le port 4200
if __name__ == "__main__":

    app.run(port=4286, debug=True)