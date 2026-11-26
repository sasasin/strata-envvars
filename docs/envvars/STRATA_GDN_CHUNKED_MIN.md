# `STRATA_GDN_CHUNKED_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の GDN prompt recurrence で、RDNA4（gfx12）の chunked WMMA scan を自動選択するときの最小トークン数を指定する。既定は `30000`。対象の `T` がこの値以上なら scan を試し、未満なら通常の recurrence に進む。値は kernel 内の自動選択しきい値だけを変え、chunk の大きさ自体は変えない（`engine/src/prefill/kernels.cu:1887-1890,1906-1909,2220-2222`）。

この読み取りと利用は `__HIPCC__` の範囲にあり、CUDA build にはこの変数による分岐がない（`engine/src/prefill/kernels.cu:2200-2204,2280-2283`）。GDN 層を処理する prompt 経路から recurrence が呼ばれる（`engine/src/prefill/prefill.cpp:5193-5210,9332-9342`）。

## 値と判定

`gdn_chunked_auto` 内の関数ローカル `static const int64_t` を初回評価時に一度だけ初期化する。未設定または空文字なら `30000`、それ以外は `std::atoll` の戻り値を使う。コードは終端位置・errno・値域を検査せず、clamp もしない（`engine/src/prefill/kernels.cu:1906-1909`）。`atoll` の数値変換では先頭の空白と符号を許し、先頭の10進数字列を変換し、数字列の後ろは検査しない。数字が始まらない文字列は `0` として扱われる。

| 条件 | unset | 有効になる値・例 | 無効になる値・例 |
| --- | --- | --- | --- |
| gfx12 の自動選択しきい値 | `30000` | `64` なら `T >= 64`、`30000` なら `T >= 30000`。`-1`、`0`、`12junk` はそれぞれ `-1`、`0`、`12` となり、独立した `T >= 64` 条件を満たす呼び出しでは実質すべての対象長を通す | `30001` のとき `T=30000` は通さない。`true` や `junk` は変換結果 `0` となるため、対象長 `T >= 64` は通る（無効文字列として拒否されるわけではない） |

`T` は GDN の prompt call/chunk の長さで、WMMA 経路には別途 `T >= 64` の条件がある。したがってしきい値を `0` や負数にしても `T < 64` の call はこの経路に入らない（`engine/src/prefill/kernels.cu:1892,2203-2205,2220-2222`）。数値としての妥当性・範囲の検証はなく、変換後の値と `T >= lo` の比較だけで決まる（同 `:1906-1909`）。

## 有効になる条件

- **HIP の gfx12 (RDNA4) device** が必要。`gdn_rec_wmma` は現在 device の GCN 名を調べ、gfx11/gfx12 以外では `false` を返す。gfx11 では `STRATA_GDN_CHUNKED` が明示的に有効な場合は chunked WMMA を使えるが、自動しきい値の判定は gfx12 に限られる（`engine/src/prefill/kernels.cu:2203-2221`）。
- `STRATA_GDN_CHUNKED` の `atoi` 結果が負（未設定・空文字も `-1`）であるときに、このしきい値が参照される。非負なら自動ゲートを通らず、`0` は chunked scan を無効にし、正数は `T >= 64` で scan を試す（同 `:1902-1909,2221-2222,2246-2249`）。
- `STRATA_GFX12_DEFAULTS` が文字 `'0'` で始まると自動選択を無効にする。文字列全体比較ではなく先頭文字判定で、たとえば `0anything` も無効。未設定、空文字、または `'0'` 以外で始まる値はこの判定では有効扱い（同 `:1906-1909`）。
- recurrence 経路では `with_out` が真で `STRATA_GDN_REC_HEADS` による serial 経路でないことが必要。WMMA scan は出力正規化を融合し、state-only の KVA 呼び出しはこの条件を満たさない（同 `:3083-3098`）。
- gfx12 の fused conv+recurrence 経路にも同じ長さゲートがある。`STRATA_GDN_FUSE=0` なら fusion を止めるが、その後の recurrence が条件を満たせば scan を選べる（同 `:2240-2265`; caller は `engine/src/prefill/prefill.cpp:5197-5210,9335-9342`）。
- Linux で**見える全カードが gfx12** の場合、`generate.cpp` は GPU の engine 初期化時に `STRATA_GDN_CHUNKED=1` を既定設定する。既存の `STRATA_GDN_CHUNKED` が空文字でも環境に存在すれば保持される。この自動注入が行われ、利用者が `STRATA_GDN_CHUNKED` を指定していない場合は chunked が明示有効扱いとなるため、`STRATA_GDN_CHUNKED_MIN` はしきい値として使われない。利用者が `STRATA_GDN_CHUNKED=` と明示して注入を抑止した場合は parser 上は未設定扱いになり、自動しきい値が使われる（`engine/src/program/generate.cpp:4304-4318`; `engine/src/core/arch_defaults.cpp:278-290`; `engine/src/prefill/kernels.cu:1902-1909`）。

## 実行時の詳細

初回の `gdn_chunked_auto` 呼び出しで `STRATA_GDN_CHUNKED_MIN` と `STRATA_GFX12_DEFAULTS` が static cache される。`STRATA_GDN_CHUNKED` の値も `gdn_chunked_env` 内で static cache されるため、これらの環境値をプロセス実行中に変更しても、この判定には反映されない。`gdn_chunked_auto` は gfx12 かつ `STRATA_GDN_CHUNKED` が負のときだけ呼ばれる（`engine/src/prefill/kernels.cu:1902-1909,2206-2222`）。

通常の recurrence では `gdn_rec_wmma` が成功すると prep/scan の kernel を launch し、その後 `check("gdn_recurrence (chunked, WMMA)")` を呼んで終了する。デバイスが非対応、出力 stride が不適合、または長さゲートを通らない場合は `false` を返し、呼び出し元が通常の recurrence kernel を選ぶ（`engine/src/prefill/kernels.cu:2203-2238,3087-3099,3247-3263,3276-3279`）。

fused 経路で fusion が無効または不適格なら、呼び出し側は別々に conv と recurrence を実行する。しきい値未満なら recurrence 側も WMMA を選ばず、通常 kernel に fallback する（`engine/src/prefill/kernels.cu:2243-2265`; `engine/src/prefill/prefill.cpp:5197-5210,9335-9342`）。

## ログと測定値

この変数を読み取ったり、その値を理由として出す専用ログはない。gfx12 で `STRATA_GDN_CHUNKED` が環境に存在せず、かつ `STRATA_GFX12_DEFAULTS` が `'0'` で始まらない場合、起動時に `strata: RDNA4 (gfx12): prompt chunks of 30,000+ tokens use the chunked GDN scan (STRATA_GDN_CHUNKED=0 turns it off)` が stderr に出る。この文言は `STRATA_GDN_CHUNKED_MIN` の値を反映せず、たとえば別のしきい値を指定しても 30,000 と表示される（`engine/src/core/arch_defaults.cpp:392-395`）。

しきい値未満のときは上記の通常 kernel fallback となり、当該ゲート自体は警告を出さない。WMMA scan の launch 後は `check("gdn_recurrence (chunked, WMMA)")` が呼ばれるが、環境変数固有の終了・エラー文言はこの判定箇所には定義されていない（`engine/src/prefill/kernels.cu:2222-2238,3095-3098`）。この調査では build・GPU 実行・測定をしていないため、実機での成否や性能値は記載しない。

## 根拠

- `engine/src/prefill/kernels.cu:1902-1909` — `STRATA_GDN_CHUNKED_MIN` の読み取り、変換、既定値、比較。
- `engine/src/prefill/kernels.cu:2203-2238,2240-2282` — HIP gfx11/gfx12 の device/length gate、fused path と fallback。
- `engine/src/prefill/kernels.cu:3083-3099,3185-3193,3247-3279` — recurrence dispatcher と通常 kernel への fallback。
- `engine/src/program/generate.cpp:4287-4318` — Linux all-gfx12 条件と startup default の適用。
- `engine/src/core/arch_defaults.cpp:278-290,392-395` — default injection の既存値優先と gfx12 起動ログ。
- `engine/src/prefill/prefill.cpp:5193-5210,9325-9342` — prompt GDN callsite と fused/regular recurrence の呼び出し。
