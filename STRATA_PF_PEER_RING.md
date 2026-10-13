# `STRATA_PF_PEER_RING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--peer-device` による multi-GPU prompt prefill で、peer GPU が primary GPU の streamed expert の一部を自分の GPU へコピーして計算するときに使う peer 側の staging ring slot 数を指定する。slot ごとに expert blob の staging buffer と「コピー完了」「計算側が使用済み」の event を持つ。未設定時は 48 slot。

## 値と判定

値は `std::atoi` で整数へ変換し、文字列全体の妥当性検証や範囲 clamp はない。

| 設定 | `RP` の値 | 結果 |
|---|---:|---|
| unset | 48 | 既定の ring slot 数 |
| `0`、空文字、数値に変換できない文字列 | 0 | slot 配列は空になる。使用時の modulo の除数にもなるため安全な無効化値として扱われていない |
| 正の整数文字列 | 変換された整数 | その数だけ slot buffer と event を用意する |
| 負の整数文字列 | 負数 | 配列サイズに `size_t` 変換して渡される。妥当性検査がなく、巨大サイズの確保要求となり setup 失敗または例外になり得る |

`atoi` のため、先頭空白や符号を含む数値の prefix は変換され、後続の非数値文字は無視される（例: `3junk` は 3）。空文字・非数値は 0 になる。値を設定しただけでは有効にならず、peer streaming 自体が有効なときだけこの変数を読む。

## 有効になる条件

- `set_peer()` を使う peer prefill 経路では、実行時に peer GPU が設定され、`--peer-prefill-rows` が 0 でないこと。peer prefill の初期化に失敗すると serve は理由を stderr に出し、その prompt path を primary GPU のみで続ける。
- peer streaming は compact peer path 内でのみ設定される。CUDA では `STRATA_PF_PEER_COMPACT=0` でも P2P がない場合 compact が強制される。SYCL では `STRATA_PF_PEER_COMPACT` の判定で compact path が決まる。
- `STRATA_PF_PEER_STREAM`（未設定時 0.35）の `atof` 結果が 0 より大きく、MMQ plan が fallback でなく、peer prefill の最大 chunk が `stream_all_min()` 以上であること。条件外では peer fraction を 0 に戻し、この ring を作らない。
- 各 chunk で primary 側の stream-all 条件 `m.ring > STAGE && T >= stream_all_min() && m.src != nullptr` も満たすこと。さらにその chunk で、resident でなく peer GPU に保持されてもいない pinned expert blob が peer streaming の対象になる。

通常利用者の peer prefill を有効にする CLI/設定と別環境変数が前提にある。layer split の prompt helper（`set_stage_helper()`）も peer GPU へ expert を送るが、そちらは `kSplitHelpRing` を使う別経路で、この環境変数を読み取らない。`docs/MULTI_GPU.md` は `--peer-device` の peer streaming と prompt prefill help の説明を区別しているが、この ring 数や許容範囲の利用者向け説明は見つからなかった。

## 実行時の詳細

peer prefill の `set_peer()` 初期化時に環境変数を読み、`PeerPrefill::RP` に保存する。環境変数は request ごとに読み直さない。条件が成立すると、slot 数分の `pstage` device buffer と `pcopied` / `pused` event を初期化する。CUDA は各 slot に最大 expert blob サイズの buffer を割り当てる。初期化時の peer buffer 確保失敗は `prefill peer: the peer's buffers do not fit ...` として呼び出し元へ返る。

chunk の peer expert 列では、entry `k` が slot `k % RP` を使う。copy stream は次の slot を再利用する前に、その slot の `pused` event を待つ。peer の計算側は対応する `pcopied` event を待ってから blob を読み、layer 内の peer-streamed entry の処理後に `pused` を記録して、その分だけ先の copy を発行する。このため ring 深度は peer 側で先行して保持できる copy 数を制御する。

ring の初期化成功時は、stderr の `strata prefill: peer GPU ... streams ... through a <RP>-slot ring` 起動ログに設定 slot 数が現れる。環境変数単独の警告や clamp のログはない。0 は無効化として分岐されず、peer entry の slot 計算で `% RP` を行うため、peer streaming 対象がある場合は不正な実行経路になる。正数でも範囲検査はなく、GPU memory 使用量は slot 数に応じて増える。

## 根拠

- CUDA の slot 初期値・読み取り・配列確保: `src/prefill/prefill.cpp:1711-1725`。
- CUDA の peer copy ring slot 回転と使用済み通知: `src/prefill/prefill.cpp:2313-2336`; peer blob の処理は同ファイル `src/prefill/prefill.cpp:3518-3540` 付近。
- CUDA の peer setup 成否、startup log、RP 表示: `src/prefill/prefill.cpp:1793-1813`。
- SYCL の同じ設定・slot 確保: `sycl/src/prefill/prefill.cpp:1768-1793`。
- SYCL の peer copy ring slot 回転: `sycl/src/prefill/prefill.cpp:2464-2505`。
- `stream_all` 条件と peer streaming の起動条件: CUDA `src/prefill/prefill.cpp:2301-2314`; SYCL `sycl/src/prefill/prefill.cpp:2460-2466`。
- peer setup の呼び出しと失敗時の primary-only 継続: CUDA `src/program/generate.cpp:7368-7373`; SYCL `sycl/src/program/generate.cpp:6941-6946`。
- layer split prompt helper が別の固定 ring を使うこと: CUDA `src/prefill/prefill.cpp:1544-1576`。
- peer prefill の利用者向け説明との照合: `docs/MULTI_GPU.md:85-101`。この資料には `STRATA_PF_PEER_RING` の既定値・値域の記載はない。
