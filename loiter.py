""" utility functions for determining if a track is a loiter """


def is_continuous(vector, maxdiff):
    """ determines if the supplied vector is continuous or discontinuous (within the 'maxdiff' tolerance) """
    # pylint: disable=consider-using-enumerate
    # i can probably come up with a smarter implementation that ignoring the pylint complaint, but not right now...
    for i in range(0, len(vector)):
        # bail if there are bad values
        if vector[i] is None:  # or (vector[i+1] is None):
            return False

        # saves two passes through the data
        if i < len(vector)-1:
            # compute sample-to-sample delta
            dv = vector[i+1]-vector[i]

            # if delta exceeds limit, mark discontinuous
            if dv > maxdiff:
                return False
    # pylint: enable=consider-using-enumerate
    return True


def unwrap_track(track):
    """ performs recursive unwrapping of a track heading to allow checking for continuity """
    wrap_limit = 180
    wraps = []
    dts = []

    track = [0 if t is None else t for t in track]
    # loop over track samples
    # pylint: disable=consider-using-enumerate
    # i can probably come up with a smarter implementation that ignoring the pylint complaint, but not right now...
    for i in range(0, len(track)):
        if i < len(track)-1:
            # compute sample-to-sample delta
            dt = track[i+1]-track[i]

            # if the delta exceeds the wrap limit, then we have a wrap
            if abs(dt) > wrap_limit:
                # note index and delta
                wraps.append(i)
                dts.append(dt)
    # pylint: enable=consider-using-enumerate

    # if we don't have any wraps, we are done
    if len(wraps) == 0:
        return track

    if len(wraps) > 1:
        # if we have more than one wrap, recurse from the second wrap to the end
        tail = unwrap_track(track[wraps[0]+1:len(track)])
        # copy wrapped 'tail' back into track vector
        track[wraps[0]+1:len(track)] = tail

    # which way do we need to unwrap?
    wrap_val = 360
    dt = track[wraps[0]+1]-track[wraps[0]]
    if dt > 0:
        wrap_val = -360

    # unwrap in proper direction
    wrapped = [x+wrap_val for x in track[wraps[0]+1:len(track)]]
    track[wraps[0]+1:len(track)] = wrapped
    return track


def is_loiter(track, time, max_time_discontinuity, loiter_degrees, loiter_trigger_duration):
    """ determines of the given track is a loiter meeting the provided configuration parameters """
    if len(time) == 0:
        return False

    if (time[-1]-time[0]) > loiter_trigger_duration:
        print("Triggering loiter due to track duration")
        print(f"time[-1]: {time[-1]}")
        print(f"time[0]: {time[0]}")
        print(f"time[-1]-time[0]: {time[-1]-time[0]}")
        print(f"loiter_trigger_duration: {loiter_trigger_duration}")
        return True
    # can't call a loiter if we aren't continuous
    if not is_continuous(time, max_time_discontinuity):
        return False
    # unwrap the track
    t2 = unwrap_track(track)
    # check for a circuit in the track heading
    # print(t2)

    return max(t2)-min(t2) >= loiter_degrees
