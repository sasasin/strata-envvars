# `FNX_PF_ATT_PIECES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の prompt attention exchange で、chunk の行を何 piece に分けて各カードへ送るかを指定します。分割処理は各 piece の attention partials を計算して送信し、受信した piece と送信完了を待って merge します。chunk の後続計算と交換を重ねるかどうかは別の overlap 条件で決まります。

## 値と判定

| 状態 | 結果 |
|---|---|
| 未設定 | 既定値 `4` |
| 設定値を整数として読み取れ、文字列全体が消費され、値が `1`〜`8` | その値を piece 数として使用 |
| 空文字、整数に変換できない文字列、末尾に未消費文字がある値、`1` 未満または `8` 超 | `std::runtime_error` で拒否 |

変換には `std::strtol(ap, &end, 10)` を使い、`end == ap`、`*end != '\0'`、範囲外を無効とします。したがって空白や符号は `strtol` の規則で先頭にあれば受け入れられ得ます（例: `+4`、` 4`）。末尾の空白や文字は文字列末尾まで消費されないため拒否されます。`0`、負値、`9`、`4x`、空文字はいずれも無効です。未設定と空文字は異なり、空文字は既定値にせずエラーになります。

## 有効になる条件

- この変数を読むのは、CMake の `STRATA_BUILD_SPLIT` で有効化される独立実行ファイル `strata-split-N` の prompt prefill 経路です。オプションは既定 OFF で、split engine は Linux CUDA または Linux HIP 向けに構成されます。通常の `strata` 実行経路にはこの読み取りはありません。
- split engine は Qwen3.8-Flash-Next の各層を2〜4枚のカードへ分割する実装です。変数値の範囲は build のカード数や backend によって変わりません。
- 分割値は attention exchange の piece 計算・送信・受信待ちに使われます。送信を次 piece の計算と重ねるコメント上の経路に加え、prefill の decode overlap に結びつく実行経路は `p.overlap` が真で、かつ `p.attn_dec` が偽の場合に `pf_attn_start` を呼びます。`p.overlap` 自体は `FNX_PF_OVERLAP` など別設定で決まります。
- `p.attn_dma` の有無で受信 piece の待機・コピー先は分岐しますが、どちらの経路も piece 数を参照します。

## 実行時の詳細

値は `Engine::prefill_alloc()` で各カードの prefill 状態を作る際に読み込まれます。`Pf` の初期値は4で、環境変数が設定されていれば検証後に上書きします。読み取りは `static` cache ではなく、各カードの初期化時に行われます。環境変数は通常プロセス起動時の値を使い、実行中に変更した場合の再評価・反映はコード上で保証されていません。

`pf_attn_start()` は `C` 行を `n` piece に分け、piece `i` の範囲を `floor(C*i/n)` から `floor(C*(i+1)/n)` として計算します。各 piece の計算後に event を記録し、送信 stream がその event を待って該当行を送り、piece 番号の flag を書きます。finish 側は各 slot の全 piece の flag を待ってから merge します。受信 DMA 経路では piece ごとに flag を待ち、host receive buffer から device buffer へコピーします。

無効値では例外メッセージ `FNX_PF_ATT_PIECES: 1 to 8, not '<値>'` が発生します。engine 構築時に捕捉され、`sfnx: failed: ...` を stderr に出し、`ERR ...` を protocol 出力へ送って終了コード1で終了します。

## 根拠

- `src/split/src/prefill.cu:312-316,355-360` — 上限8、piece 状態の既定値4。
- `src/split/src/prefill.cu:541-548,551-577,581-596` — piece ごとの送信、flag、受信待ちと merge。
- `src/split/src/prefill.cu:768-780` — `getenv` による読み取り、10進変換、全体消費・範囲検証、例外文言。
- `src/split/src/prefill.cu:1163-1171,1227-1237` — overlap あり／なし、decode attention の条件による attention 経路。
- `src/split/src/engine.cu:275` — engine 構築中に `prefill_alloc()` を呼び出す。
- `src/split/tools/sfnx.cpp:1055-1062,1027-1035` — 構築例外の捕捉、protocol error と stderr、終了コード1。
- `CMakeLists.txt:2945-2949` — split engine の opt-in build 条件。
- `src/split/CMakeLists.txt:1-7,20-30,64-79,92-120` — 独立実行ファイル、Linux CUDA/HIP 条件、対象ソースの build。
- `src/split/src/engine.hpp:66-70` — prompt path とモデル実装の説明。
