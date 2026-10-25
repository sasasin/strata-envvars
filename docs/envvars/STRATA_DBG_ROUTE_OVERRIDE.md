# `STRATA_DBG_ROUTE_OVERRIDE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

MoE の prompt prefill で通常の router が選んだ expert ID と重みを、指定ファイル内のレコードに一致する layer・token chunk の値で置き換えます。コードコメントでは `141-research` の opt-in research hook と明記されています。decode 用の router を切り替える設定ではありません。

## 値と判定

値はファイルパスとして扱われ、真偽値や数値への parse はありません。`getenv()` が非 null かどうかでフックを有効にします。

| 環境変数の状態 | 動作 |
|---|---|
| unset | `STRATA_DBG_FEAT` も unset なら、このフックの同期・ファイル読込・上書き処理に入らない。 |
| 空文字 | 設定済みとしてフックに入るが、空パスを `fopen(..., "rb")` で開けず override map は空。MoE chunk ごとの同期は行われる。 |
| 開けるパス | 起動後の最初のフック実行時にファイルを読み、レコードを map にする。 |
| 開けないパス | map は空のまま戻り、override は起きない。明示的なエラー表示はない。 |

ファイルはレコードを連結したバイナリとして読みます。各レコードは native 表現の `int32_t` 3 個（layer、position、T）に続けて、`T * 10` 個の `int32_t` expert ID、その後 `T * 10` 個の `float` weight です。読み込み側は expert 数を 10 と固定し、モデル geometry の `ss.k == 10` を別途要求します。レコードキーは `(layer, position)` で、重複キーは後に読んだレコードが map 内の値を置き換えます。形式の version、endianness、weight 値域、header の T に対する明示的な妥当性検査はありません。完全でない header または配列を読んだ時点で読み込みを止め、それまでに読み込めたレコードを使います。

## 有効になる条件

- `src/prefill/prefill.cpp` の GPU prompt prefill が実行され、MoE 層の router 計算まで到達する必要があります。通常の router 結果を作った後に override を探します。
- `STRATA_DBG_FEAT` が設定されている場合も同じフックに入ります。これは別の dump 機能ですが、route override が unset なら override map は空です。逆に route override だけが設定されているとき、feature dump 用ファイルは開きません。
- レコードの layer と position が現在の chunk に一致し、保存された ID 数が現在の `T * K`（`K=10`）と一致した場合だけ上書きします。レコードがない、または T が一致しない場合は router の出力を維持します。
- 置き換え後の ID は後続処理で `0 <= id < n_expert` を検査し、範囲外なら `prefill: routed id out of range` で prefill を失敗させます。weight に同様の範囲検査はこのフックにはありません。

## 実行時の詳細

環境変数と override map はフック内の function-local `static` として初期化されます。最初にこのブロックへ到達した時の環境・ファイル内容がプロセス内で再利用されるため、実行中に環境変数やファイルを書き換えても再読込されません。最初の到達時に両変数が unset なら後で設定しても有効になりません。

position は layer ごとの `posl[64]` カウンタから得て、chunk の `T` を加算します。したがって照合値は prompt 内でその layer が処理した token の chunk 開始位置です。map を作成できた場合は stderr に `route override: %zu records` と読み込んだレコード数を出します。ファイルを開けなかった場合、このログも出ません。

フックは現在の CUDA stream を同期してから host 上で router 出力を必要に応じて差し替えます。空文字や不正パスでも環境変数が設定済みなら、map が空でもこの同期経路に入ります。

## 根拠

- `src/prefill/prefill.cpp:2867-2869` — router 実行後にフックへ進む。
- `src/prefill/prefill.cpp:2870-2903` — research hook の位置づけ、環境変数の取得、バイナリレコード読込、map 作成とログ。
- `src/prefill/prefill.cpp:2904-2906` — layer ごとの chunk position と stream 同期。
- `src/prefill/prefill.cpp:2923-2927` — layer・position・要素数が一致した場合の ID / weight 差し替え。
- `src/prefill/prefill.cpp:102` — `K=10`。
- `src/prefill/prefill.cpp:3170-3173` — 後続の routed ID 範囲検査。
- `docs/DETAILS.md` にこの変数の説明や測定値は見つからなかった。
