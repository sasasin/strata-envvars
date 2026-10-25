# `--spec-min-p`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。調査時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--spec-min-p P` |
| 別名 | なし |
| 値 | ドラフト層の各候補の確率閾値 `P`。既定値 `0.0` |

## 役割

MTP の speculative decoding で、ドラフト層の候補確率が `P` 以上の間だけ verify window を次のドラフト候補へ延ばします。既定値の `0` は確率による打ち切りを無効にし、`--spec` で決めた窓幅まで候補を使います（`src/program/generate.cpp:703-705,938-941,16536-16543`; `src/core/mtp.cpp:1689`）。

## 使い方

```sh
strata generate --pack ./model-pack --tokens "1,2,3" --mtp ./model-mtp --spec 4 --spec-min-p 0.5
```

モデル・pack と MTP のパスは環境に合わせてください。`--spec` は MTP の verify window 幅を指定し、MTP を使わない実行ではこの閾値による speculative window 選択は行われません（`src/program/generate.cpp:938-941,14880-14888,16536-16543`）。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。未指定時は `0.0` です（`src/program/generate.cpp:705,2630`）。
- CLI parser は値の範囲検査や clamp をしません。`P <= 0` の場合、window の確率閾値判定は無効です。`P > 1` の場合は通常の確率値が閾値を満たさないため、window は最小幅になります（`src/program/generate.cpp:16540-16543`; `src/core/mtp.cpp:1689`）。
- 数値変換の失敗を個別に検出する処理はありません。オプションを複数回指定すると parser が順に代入し、最後に読んだ値が残ります（`src/program/generate.cpp:2416-2421,2630`）。
- 値を省略すると `--spec-min-p needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

通常の MTP 経路では、各ドラフト候補の確率を順に調べ、確率が `P` 未満になった位置でドラフト連鎖を終えます。verify window の幅選択でも、最初の候補から各確率が `P` 以上である間だけ `T` を増やします。したがってこのオプションは累積確率ではなく、各候補単独の確率を基準にします（`src/core/mtp.cpp:1689`; `src/program/generate.cpp:16540-16543`）。

`--serve` では起動時の `o.spec_min_p` が各リクエストの初期値になります。リクエスト文字列に `spec_min_p=...` がある場合、その値を `0.0`〜`1.0` に clamp して当該リクエストの window 選択・MTP draft に使います（`src/program/generate.cpp:12315-12318,12325-12352,14354-14361,14880-14888,15168-15170`）。これは CLI 引数自体の clamp とは別の処理です。

DFlash2 を使う場合、正の `--draft-conf` は verify window の幅選択で `--spec-min-p` に代わり、selector 確率の積を基準にします。`--draft-conf` が有効でないときの DFlash2 window と、MTP fallback 側のドラフト生成は引き続き `--spec-min-p` を参照します（`src/program/generate.cpp:795,16511-16512,16529,16540-16549`）。また `STRATA_SPEC_COST=1` が有効な経路では、MTP window は確率閾値ではなく測定済みコスト方針で選ばれます（`src/program/generate.cpp:16400-16403,16538-16543`）。

## 適用条件と副作用

この値が制御するのは MTP / DFlash2 の speculative draft と verify window です。`--spec-min-p` 自体はファイルやネットワークを扱いません。MTP が使われない場合は閾値による window 調整はありません（`src/program/generate.cpp:14880-14888,16536-16543`）。

## 出力とエラー

非 serve の生成終了時、`P > 0` なら stdout に window サイズの集計と `(min draft probability P)` が表示されます。`P <= 0` の場合この集計行は出ません（`src/program/generate.cpp:16727-16738`）。

ドラフト生成が失敗した場合は `strata generate: <理由>` を stderr に出して終了コード `1` となる経路があります。値の欠落は終了コード `2`、未知の引数も `unknown argument` と usage を stderr に出して `2` で終了します（`src/program/generate.cpp:16411-16415,2418-2420,2787-2793`）。

## 根拠

- `src/program/generate.cpp:703-705,938-941` — オプションの役割、既定値、usage。
- `src/program/generate.cpp:2416-2421,2630` — CLI parser、値取得と代入。
- `src/core/mtp.cpp:1689` — MTP draft chain が確率閾値で候補を打ち切る条件。
- `src/program/generate.cpp:12315-12318,12325-12352,14354-14361,14880-14888,15168-15170` — serve リクエスト単位の値と clamp、window/draft への適用。
- `src/program/generate.cpp:16400-16403,16538-16549,16727-16738` — コスト方針、DFlash2 との相互作用、終了時の集計。
- `src/program/generate.cpp:16411-16415,2787-2793` — draft 失敗と未知引数の終了経路。

本調査では既存 CLI の help を実行せず、Release artifact や各 GPU/backend での挙動も確認していません。記述は上記 checkout のソースに基づきます。
