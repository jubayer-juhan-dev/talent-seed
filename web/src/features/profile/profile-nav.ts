/** Opening a profile pushes a history entry, so Back closes it. Closing goes back when we pushed that entry
 *  ourselves, and otherwise (a shared link opened directly) just removes ?p= so Back doesn't leave the app. */
let pushedHere = false;
export const markProfilePushed = () => {
  pushedHere = true;
};
export const takeProfilePushed = () => {
  const was = pushedHere;
  pushedHere = false;
  return was;
};
