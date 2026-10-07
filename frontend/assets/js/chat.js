var checkout = {};
// communication to lex 
var sessionId = window.crypto.getRandomValues(new Uint32Array(4)).join("-");

$(document).ready(function() {
  var $messages = $('.messages');
  var $messageList = $('.messages-content');

  insertResponseMessage('Hi there, I\'m your personal Concierge. How can I help?');

  function scrollToBottom() {
    window.requestAnimationFrame(function() {
      $messages.scrollTop($messages[0].scrollHeight);
    });
  }

  function setDate($message) {
    var date = new Date();
    var hours = String(date.getHours()).padStart(2, '0');
    var minutes = String(date.getMinutes()).padStart(2, '0');
    $('<div class="timestamp">').text(hours + ':' + minutes).appendTo($message);
  }

  function callChatbotApi(message) {
    // params, body, additionalParams
    return sdk.chatbotPost({}, {
      messages: [{
        type: 'unstructured',
        unstructured: {
          id: sessionId,
          text: message
        }
      }]
    }, {});
  }

  function insertMessage() {
    var msg = $('.message-input').val();
    if ($.trim(msg) == '') {
      return false;
    }
    var $message = $('<div class="message message-personal">')
      .text(msg).appendTo($messageList).addClass('new');
    setDate($message);
    $('.message-input').val(null);
    scrollToBottom();

    callChatbotApi(msg)
      .then((response) => {
        console.log(response);
        var data = response.data;

        if (data.messages && data.messages.length > 0) {
          console.log('received ' + data.messages.length + ' messages');

          var messages = data.messages;

          for (var message of messages) {
            if (message.type === 'unstructured') {
              insertResponseMessage(message.unstructured.text);
            } else if (message.type === 'structured' && message.structured.type === 'product') {
              var html = '';

              insertResponseMessage(message.structured.text);

              setTimeout(function() {
                html = '<img src="' + message.structured.payload.imageUrl + '" witdth="200" height="240" class="thumbnail" /><b>' +
                  message.structured.payload.name + '<br>$' +
                  message.structured.payload.price +
                  '</b><br><a href="#" onclick="' + message.structured.payload.clickAction + '()">' +
                  message.structured.payload.buttonLabel + '</a>';
                insertResponseMessage(html);
              }, 1100);
            } else {
              console.log('not implemented');
            }
          }
        } else {
          insertResponseMessage('Oops, something went wrong. Please try again.');
        }
      })
      .catch((error) => {
        console.log('an error occurred', error);
        insertResponseMessage('Oops, something went wrong. Please try again.');
      });
  }

  $('.message-submit').click(function() {
    insertMessage();
  });

  $(window).on('keydown', function(e) {
    if (e.which == 13) {
      insertMessage();
      return false;
    }
  })

  function insertResponseMessage(content) {
    var $loading = $('<div class="message loading new"><figure class="avatar"><img src="https://media.tenor.com/images/4c347ea7198af12fd0a66790515f958f/tenor.gif" /></figure><span></span></div>').appendTo($messageList);
    scrollToBottom();

    setTimeout(function() {
      $loading.remove();
      var $message = $('<div class="message new"><figure class="avatar"><img src="https://media.tenor.com/images/4c347ea7198af12fd0a66790515f958f/tenor.gif" /></figure>' + content + '</div>').appendTo($messageList);
      setDate($message);
      scrollToBottom();
    }, 500);
  }

});
