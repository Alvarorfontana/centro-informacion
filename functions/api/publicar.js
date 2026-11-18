import handler from '../../api/publicar.js';
import { adaptar } from '../_vercel.js';
export const onRequest = adaptar(handler);
