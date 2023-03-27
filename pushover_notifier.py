
import pushover

class NotifierFunctor:
  def __init__(self,config):
    pass
  
  def __call__(self,config,title,msg_text,priority,sound,url):
    po=pushover.Pushover(config["pushover_api_key"]);
    po.user(config["pushover_user_key"]);
    msg=po.msg(msg_text);
    msg.set('title',title);
    msg.set('priority',priority);
    if sound is not None:
      msg.set('sound', sound);
    if url is not None:
      msg.set('url', url);
    return po.send(msg);

