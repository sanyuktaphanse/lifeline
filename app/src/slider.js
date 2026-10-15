// Slide to start: the knob finishes only once it has travelled four fifths of its track, so a short drag springs
// back. The knob is a button, so Enter or Space starts at once, and the welcome keeps a plain button as well.
const FINISH = 0.8;

export function slideDone(x, max) {
  return max > 0 && x >= max * FINISH;
}
