from bson.objectid import ObjectId
from cloudinary.uploader import upload, destroy
from flask import redirect, url_for, render_template, request, session, abort

from app import app
from app.setup import DB_RECIPES, DB_INGREDIENTS, DB_METHODS, DB_USERS, TODAY_STR


####################
# MAIN RECIPE VIEW #
####################
@app.route('/recipe/<recipe_id>')
def recipe(recipe_id):
    """ Returns the main recipe view

     :return
         Renders recipe.html

    """
    current_recipe = None
    current_recipe_author = None
    current_recipe_ingredients = None
    current_recipe_methods = None

    try:
        current_recipe = DB_RECIPES.find_one({'_id': ObjectId(recipe_id)})
        current_recipe_author = DB_USERS.find_one({'_id': ObjectId(current_recipe['author_id'])})
        current_recipe_ingredients = DB_INGREDIENTS.find({'recipe_id': ObjectId(recipe_id)})
        current_recipe_methods = DB_METHODS.find({'recipe_id': ObjectId(recipe_id)})
    except:
        # raises a 404 error if any of these fail
        abort(404, description="Resource not found")
    # Set loged in variable
    loged_in = False
    if session.get('USERNAME', None):
        username = session['USERNAME']
        user = DB_USERS.find_one({'username': username})
        favorites = user['favorites']
        loged_in = True
    else:
        favorites = []

    return render_template('recipe.html', current_recipe=current_recipe, current_recipe_author=current_recipe_author,
                           current_recipe_ingredients=current_recipe_ingredients,
                           current_recipe_methods=current_recipe_methods, favorites=favorites, loged_in=loged_in)


###############
# TEMP RECIPE #
###############
@app.route('/add_temp_recipe/<user_id>')
def add_temp_recipe(user_id):
    """ Creates a temporary recipe record to assign to the user
     :return
         Redirect to edit_recipe url
    """
    # User exists in the database and Signed in
    if session.get('USERNAME', None):
        username = session['USERNAME']
        # user exists in the database
        try:
            current_user = DB_USERS.find_one({'username': username})
            requested_user = DB_USERS.find_one({'_id': ObjectId(user_id)})
            # if the current logged in user is the user requested
            if requested_user['_id'] == current_user['_id']:
                # Default recipe image
                image_url = 'https://res.cloudinary.com/dajuujhvs/image/upload/v1591896759/gi5h7ejymbig1yybptcy.png'
                image_url_id = 'gi5h7ejymbig1yybptcy'
                # create empty temp record
                temp_record = DB_RECIPES.insert_one(
                    {
                        'name': 'My Awesome Recipe',
                        'image_url': image_url,
                        'image_url_id': image_url_id,
                        'featured': 'false',
                        'current_rating': '0',
                        'total_ratings': 0,
                        'sum_ratings': 0,
                        'author_id': ObjectId(user_id),
                        'preptime_hrs': '0',
                        'preptime_min': '0',
                        'cooktime_hrs': '0',
                        'cooktime_min': '0'
                    })
                return redirect(url_for('edit_recipe', user_id=user_id, recipe_id=temp_record.inserted_id))
            else:
                # raises a 403 error
                return abort(403, description="Forbidden")
        except:
            # raises a 404
            return abort(404, description="Resource not found")
    else:
        # User not signed in
        return redirect(url_for('sign_in'))


####################
# EDIT RECIPE VIEW #
####################
@app.route('/edit_recipe/<user_id>/<recipe_id>')
def edit_recipe(user_id, recipe_id):
    """ Renders the edit-recipe template passing in the temporary recipe id
     :return
         returns the edit-recipe.html form
    """
    # User not Signed in
    if not session.get('USERNAME', None):
        return redirect(url_for('sign_in'))

    username = session['USERNAME']
    # user exists in the database
    try:
        current_user = DB_USERS.find_one({'username': username})
        current_recipe = DB_RECIPES.find_one({'_id': ObjectId(recipe_id)})
        current_ingredients = DB_INGREDIENTS.find({'recipe_id': current_recipe['_id']})
        current_methods = DB_METHODS.find({'recipe_id': current_recipe['_id']})
        # if the current logged in user is recipe author
        if current_recipe['author_id'] == current_user['_id']:
            return render_template('edit-recipe.html', user_id=user_id, recipe_id=recipe_id,
                                   current_recipe=current_recipe,
                                   current_ingredients=current_ingredients, current_methods=current_methods)
        else:
            # raises a 403 error
            return abort(403, description="Forbidden")
    except:
        # raises a 404 error if any of these fail
        return abort(404, description="Resource not found")


#################
# UPDATE RECIPE #
#################
@app.route('/update_recipe/<user_id>/<recipe_id>', methods=['POST'])
def update_recipe(user_id, recipe_id):
    """ Updates the recipe database record

    :return
        returns the edit-recipe.html form overview tab

    """
    # User not Signed in
    if not session.get('USERNAME', None):
        return redirect(url_for('sign_in'))

    try:
        # get the current user's record
        current_user = DB_USERS.find_one({'_id': ObjectId(user_id)})

        # update the recipe record
        DB_RECIPES.update_one({'_id': ObjectId(recipe_id)}, {"$set": {
            'name': request.form.get('recipe-name'),
            'description': request.form.get('recipe-description'),
            'notes': request.form.get('recipe-notes'),
            'preptime_hrs': request.form.get('prep-hours'),
            'preptime_min': request.form.get('prep-minutes'),
            'cooktime_hrs': request.form.get('cook-hours'),
            'cooktime_min': request.form.get('cook-minutes'),
            'serves': request.form.get('serves'),
            'author': current_user['username'],
            'author_id': ObjectId(user_id),
            'date_updated': TODAY_STR
        }}, upsert=True)
        # return to recipe overview page
        return redirect(url_for('edit_recipe', _anchor='overview', user_id=user_id, recipe_id=recipe_id))
    except:
        # raises a 404 error if any of these fail
        return abort(404, description="Resource not found")


#######################
# UPDATE RECIPE IMAGE #
#######################
@app.route('/update_recipe_image/<user_id>/<recipe_id>', methods=['POST'])
def update_recipe_image(user_id, recipe_id):
    """ Updates the recipe image in cloudinary

    :return
        returns the edit-recipe.html form image tab with updated image

    """
    # User not Signed in
    if not session.get('USERNAME', None):
        return redirect(url_for('sign_in'))

    # get the file from the form
    file_to_upload = request.files.get('file')

    if file_to_upload:
        # get the current recipe record
        current_recipe = DB_RECIPES.find_one({'_id': ObjectId(recipe_id)})
        # delete the current recipe image on cloudinary
        if current_recipe['image_url_id'] != 'gi5h7ejymbig1yybptcy':
            destroy(current_recipe['image_url_id'], invalidate=True)
        # upload the new image
        upload_result = upload(file_to_upload)

        # update record
        DB_RECIPES.update_one({'_id': ObjectId(recipe_id)}, {"$set": {
            'image_url': upload_result['secure_url'],
            'image_url_id': upload_result['public_id'],
            'date_updated': TODAY_STR
        }}, upsert=True)

    return redirect(url_for('edit_recipe', _anchor='image', user_id=user_id, recipe_id=recipe_id))


#################
# DELETE RECIPE #
#################
@app.route('/delete_recipe/<recipe_id>')
def del_recipe(recipe_id):
    """ Deletes the recipe from the database

   :return
       Redirects to the user's profile url

   """
    # User not Signed in
    if not session.get('USERNAME', None):
        return redirect(url_for('sign_in'))
    # Get username
    username = session['USERNAME']
    try:
        current_user = DB_USERS.find_one({'username': username})
        current_recipe = DB_RECIPES.find_one({'_id': ObjectId(recipe_id)})
        # if the current logged in user is recipe author
        if current_recipe['author_id'] == current_user['_id']:
            DB_RECIPES.remove({'_id': ObjectId(recipe_id)})
            DB_INGREDIENTS.delete_many({'recipe_id': ObjectId(recipe_id)})
            DB_METHODS.delete_many({'recipe_id': ObjectId(recipe_id)})

            return redirect(url_for('profile'))

    except:
        # raises a 404 error if any of these fail
        return abort(404, description="Resource not found")


##################
# ADD INGREDIENT #
##################
@app.route('/add_ingredient_item/<user_id>/<recipe_id>', methods=['POST'])
def add_ingredient_item(user_id, recipe_id):
    """ Adds an ingredient to the database and references the recipe id

    :return
        returns the edit-recipe.html form ingredient tab with updated ingredient list

    """
    # Insert ingredient record
    DB_INGREDIENTS.insert_one(
        {'ingredient_item': request.form.get('ingredient_item'), 'recipe_id': ObjectId(recipe_id),
         'author_id': ObjectId(user_id)})

    return redirect(url_for('edit_recipe', _anchor='ingredients', user_id=user_id, recipe_id=recipe_id))


#####################
# DELETE INGREDIENT #
#####################
@app.route('/delete_ingredient_item/<user_id>/<recipe_id>/<ingredient_id>')
def del_ingredient_item(user_id, recipe_id, ingredient_id):
    """ Deletes an ingredient to the database from the recipe id reference

    :return
        returns the edit-recipe.html form ingredient tab with updated ingredient list

    """
    # Remove ingredient record
    DB_INGREDIENTS.remove({'_id': ObjectId(ingredient_id)})

    return redirect(url_for('edit_recipe', _anchor='ingredients', user_id=user_id, recipe_id=recipe_id))


###################
# ADD METHOD ITEM #
###################
@app.route('/add_method_item/<user_id>/<recipe_id>', methods=['POST'])
def add_method_item(user_id, recipe_id):
    """ Adds a method to the database and references the recipe id

    :return
        returns the edit-recipe.html form method tab with updated method list

    """
    # Insert method record
    DB_METHODS.insert_one(
        {'method_name': request.form.get('method_name'), 'recipe_id': ObjectId(recipe_id),
         'author_id': ObjectId(user_id)})

    return redirect(url_for('edit_recipe', _anchor='method', user_id=user_id, recipe_id=recipe_id))


######################
# DELETE METHOD ITEM #
######################
@app.route('/delete_method_item/<user_id>/<recipe_id>/<method_id>')
def del_method_item(user_id, recipe_id, method_id):
    """ Deletes an method to the database from the recipe id reference

    :return
        returns the edit-recipe.html form method tab with updated method list

    """
    # Remove method record
    DB_METHODS.remove({'_id': ObjectId(method_id)})

    return redirect(url_for('edit_recipe', _anchor='method', user_id=user_id, recipe_id=recipe_id))


###############
# RATE RECIPE #
###############
@app.route('/rate_recipe/<recipe_id>', methods=['POST'])
def rate_recipe(recipe_id):
    """ Updates the recipe rating and number of ratings

    :return
        Redirect to recipe page
    """
    try:
        # calculate new rating
        current_recipe = DB_RECIPES.find_one({'_id': ObjectId(recipe_id)})
        calculated_rating_total = int(current_recipe['total_ratings']) + 1
        calculated_sum = int(current_recipe['sum_ratings']) + int(request.form.get('rating'))
        # rounded average for simplicity
        calculated_avg = round(calculated_sum / calculated_rating_total)
        # update record
        DB_RECIPES.update_one({'_id': ObjectId(recipe_id)}, {"$set": {
            'total_ratings': calculated_rating_total,
            'sum_ratings': calculated_sum,
            'current_rating': calculated_avg
        }}, upsert=True)

    except:
        # raises a 404 error if any of these fail
        return abort(404, description="Resource not found")
    return redirect(url_for('recipe', recipe_id=recipe_id))
