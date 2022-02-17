const TIME_BEFORE_IN_SECONDS = 1.5;
const TIME_AFTER_IN_SECONDS = 1.5;
const AD_DURATION = 5.0;

const REASON_PRETTY_NAME_BY_OPERATOR_NAME = {
  'Silences': 'Silence',
  'BlackFrames': 'Black frame',
  'SceneChanges': 'Shot change',
  'EndCredits': 'End Credits',
  'FadeIns': 'Fade In',
  'FadeOuts': 'Fade Out'
};

const TOOLTIP_BY_OPERATOR_NAME = {
  'Silences': 'Short-term loudness lower than -50dB',
  'BlackFrames': 'More than 98% black frame',
  'SceneChanges': 'Hard cut from one frame to the next',
  'EndCredits': 'Cast and crew credits at the end of the video',
  'FadeIns': 'More than 95% frame change from black',
  'FadeOuts': 'More than 95% frame change to black'
};

const VMAP_GENERATOR_API_URL = 'https://w2j76rw9jc.execute-api.us-east-1.amazonaws.com/Prod/vmap-generator'
const MEDIATAILOR_URL = 'https://af813ac4abc54e658800cc12499df9ed.mediatailor.us-east-1.amazonaws.com/v1/master/27dd94f37203d33fbc56f834c21ddc067dec03f3/nab-demo/'

// Get video id from URL. The id will be used to load the data from data.js file
// Example http://127.0.0.1:8080/?id=1 (id is 1)
var videoDataId = new URLSearchParams(window.location.search.substring(1)).get('id');
if (!videoDataId) {  // Redirect to id 1 if no id is provided
  window.location.replace('/?id=' + defaultId);
}
var videoData = data.find(element => element.id == videoDataId);

// Add show attribute to all slots
videoData['slots'].map(slot => slot['show'] = true);

var player = videojs('my-player');
player.src({type: 'video/mp4', src: videoData.path});

// Video pause time logic
var pauseTime = Number.MAX_SAFE_INTEGER;
document.getElementById('my-player').onclick = function changeContent() {
  pauseTime = Number.MAX_SAFE_INTEGER;
};
player.on('timeupdate', function() {
  if (player.currentTime() >= pauseTime) {
      player.pause();
  }
});
player.on('durationchange', function() {
  console.log('duration changed: '+ player.duration());
  if (player.markers.reset) {
    player.markers.reset([].concat(player.markers.getMarkers()));
  }
});

function updateMarkers(slots, includeAds=false) {
  console.log('updating markers')
  var markers = [];
  var offset = 0.0;
  sortedSlots = sortByKey(slots, 'time', false);
  for (let slot of sortedSlots) {
    var text = 'Slot ' + slot.id;
    markers.push({
      time: slot.time + offset,
      duration: includeAds && slot.checked ? AD_DURATION : 0.0,
      text: text,
      overlayText: text,
      class: slot.checked ? 'checked-marker' : 'unchecked-marker'
    });
    if (includeAds && slot.checked) {
      offset += AD_DURATION;
    }
  }
  if (typeof player.markers == 'object') {
    player.markers.reset(markers);
    return;
  }
  player.markers({markers: markers});
}

function sortByKey(array, key, desc=false) {
  return array.sort(function(a, b) {
    var x = a[key]; var y = b[key];
    return (desc ? -1 : 1) * ((x < y) ? -1 : ((x > y) ? 1 : 0));
  });
}

var contextTabs = new Vue({
  el: '#context',
  data: {
    selectedSlotId: -1,
    slots: videoData.slots
  },
  filters: {
    confidenceFormat: function(value) {
      var confidence = parseFloat(value)
      return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(confidence);
    }
  },
  computed: {
    selectedContext: function() {
      if (this.selectedSlotId >= 0) {
        return this.slots.filter(slot => slot.id == this.selectedSlotId)[0].context;
      }
    }
  }
});

new Vue({
  el: '#slots',
  data: {
    selectedSlotId: -1,
    slots: videoData.slots,
    vmapUrl: undefined,
    showAds: false
  },
  computed: {
    sortedSlots: function() {
       return sortByKey(this.slots, 'score', true);
    },
    checkedCount: function() {
       return this.slots.filter(slot => slot.checked).length;
    }
  },
  methods: {
    selectSlot: function(slot) {
      contextTabs.selectedSlotId = slot.id;
      this.selectedSlotId = slot.id;
      pauseTime = slot.time + TIME_AFTER_IN_SECONDS;
      player.currentTime(slot.time - TIME_BEFORE_IN_SECONDS);
      player.play();
      window.scrollTo(0, 0);
    },
    checkSlot: function(slot) {
      slot.checked = !slot.checked;
      updateMarkers(this.slots);
    },
    closeSlot: function(slot) {
      slot.checked = false;
      slot.show = false;
    },
    saveSlots: function(slots) {
      checkedSlots = slots.filter(slot => {
        return slot.checked;
      });
      axios.post(VMAP_GENERATOR_API_URL, {
        assetId: videoDataId,
        slots: checkedSlots
      }).then(response => {
        this.vmapUrl = response.data.vmapUrl;
      }).catch(error => {
        console.log(error);
      });
    },
    downloadVmap: function() {
      console.log('vmapUrl: '+ this.vmapUrl)
      const link = document.createElement('a')
      link.href = this.vmapUrl
      link.setAttribute('download', videoDataId + '.vmap')
      document.body.appendChild(link)
      link.click()
    },
    updatePlayer: function() {
      console.log('showAds: '+ this.showAds)
      updateMarkers(this.slots, this.showAds)
      if (this.showAds) {
        player.src({type: 'application/x-mpegURL', src: MEDIATAILOR_URL + videoDataId + '.m3u8?ads.asset_id=' + videoDataId});
      } else {
        player.src({type: 'video/mp4', src: videoData.path});
      }
    },
    getTooltip: function(reason) {
      return TOOLTIP_BY_OPERATOR_NAME[reason];
    }
  },
  filters: {
    timeFormat: function(value) {
      var duration = moment.duration(value, 'seconds');
      return moment.utc(duration.as('milliseconds')).format('HH:mm:ss');
    },
    scoreFormat: function(value) {
      var score = value * 100.0;
      return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(score);
    },
    reasonPrettyName: function(value) {
      return REASON_PRETTY_NAME_BY_OPERATOR_NAME[value]
    }
  },
  mounted: function () {
    this.$nextTick(function () {
      updateMarkers(this.slots)
    });
  }
});

// Tooltips Initialization
$('[data-toggle="tooltip"]').tooltip();
