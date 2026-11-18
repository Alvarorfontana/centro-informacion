import handler from '../../api/reformular.js';
import { adaptar } from '../_vercel.js';
export const onRequest = adaptar(handler);
