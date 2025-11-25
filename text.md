So now we are gonna  have to create a microservice, if you look at @beautifulMentiontelegram_bot.py, at line 893 in function async def finish_message_flow(message: Message, state: FSMContext): we are only saving the message to database which is correct, but the whole idea of the project is to route this messsage to the right department  and to do that we need create microservice in which there is gonna be injection detecor  vector database qdrant (right now running and ready on docker) and gemini. So the overall view of the microservice, is inside telegram_bot.py in fuction async def finish_message_flow(message: Message, state: FSMContext): once we have tsaved the message we have to call the api of our microservice and pass a json like that 
{
  "message_uuid": "91b52e2e-4f5d-4bd7-a12e-3b04c99b9f47",
  "user": {
    "uuid": "c6f0b2c1-55a0-4c92-86e1-89ce64f0c921",
    "full_name": "Umarov Javohir",
    "telegram_user_id": 556677889,
    "email": null
  },
  "message": {
    "text": "Salom, suv hisoblagichim ishlamayapti.",
    "sent_at": "2025-02-03T14:22:18Z"
  },
  "settings": {
    "model": "gemini-2.5-pro",
    "temperature": 0.2,
    "max_tokens": 500,
    "auto_detect_language": true
  }
}


once the microservice recieves it, it has pass the message through a simple injection detector, you may have to create a py file and inisde injector dector function, which you will pass the text though , if it returns in_injection: true, then you have to call an api that calls the function to send a emergency notification to System Admin dasboard(since we do not have it, you just leave a placeholder function) and plus in our microservice the operation should be ternminated and everything and then you have to vectorize the text with gemini emedding models, and then you call the deparments vector database to do search to find the matching department to the text, deparment table could be like this {
  "department_id": 1,
  "keywords": ["I lost my passport",
  "vector": [0.12, -0.44, 1.08, ...]
}

and it should produce output of 3 best canditates with the hihgst confidence rate: and then you have take result of vector database and the text of the user the message and then create a json enforced prompt, 







There is a slight problem, so once a conversation chat is open, we shoudl have a column conversation_closed: false or true, which it will be determined bythe decision of the admin , if closed, it is permanently closed and can't be opened. That is for web though, it is easy to do that when the operation is only web based but the problem is that we have dual channel problem, let''s say the conversation is open, but we are providing the ability to continue the conversation from telegram as well. for telegram it needs to create inidividual messages and send them to the both dashboard and telegram of the admin, so we can't possibly make decision if this is a conversation in telegram, but the thing that we are sending to deparment dashboard where all admins have access to, creates possibility that we can figure out if this is a conversation cuz admin is responsible for closing the conversation. So it has become complex and feels little misshaped to me. cuz usually in web it is the fronted javascript that creates the message_uuid, or is it also done in database like mysql itself. Cuz if you let the user continue conversation in telegram that started in web, you letting in mycase backend to create message_uuid and sending it to dashboard, which is usually the fronted that is creating uuid,. You know what this has become so confusing, tell me in my case is the message_uuid is being created in mysql itself automatically or backend . and what about frontend if i will have a dashboard the message_uiid should be created in backend not in fronted i think that is way more correct yeah. Assuming that i will rely on creating messagee_uuids on backend or maybe mysql itself autogenerates it. So i think we have two options, either we merge the conversations that happens in web and telgram and allow continuity from both platfroms which is messy or make them platfrom specific, like message from web goes to web, telegram to telegram , but the problem with that is that, governemnt admins prefer working on computer so their choice is often website than telegram like 99percent of the time. So these message sent from telegram also should arrive at web dashboard, then it is option 1 , that we have to go. 
then message_uuid for both web and telegram should be created by unified function inside backend, and conversation_uuid is the same for all messages untill the admin closes it. 