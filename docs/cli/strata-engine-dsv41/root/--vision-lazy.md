# `--vision-lazy`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--vision-lazy` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--vision-lazy` は現在も引数として受理されますが、この revision では指定しても動作を切り替えません。serve モードでは、独立した `--vision-resident` を指定しない限り、離散 GPU 上の vision tower を画像処理の間だけ GPU に載せる方式が既定です。parser は `--vision-lazy` を読んだ印を立てるだけで、その印は後続処理で参照されません（`src/dsv41/ds4_main.cpp:2506,2553,2620`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --serve --vision-lazy
```

この例の `--vision-lazy` は互換性のために受理されます。serve 時の遅延ロード方式を明示的に選ぶ効果はありません。vision tower を GPU 上に保持する指定は次のとおりです。

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --serve --vision-resident
```

## 値と既定値

値を取りません。`--vision-lazy` の有無にかかわらず、その値を検証・保存する処理はありません。複数回指定しても同じです。直後に別の裸の引数を置くと、その引数は別 option として処理され、未知ならエラーになります（`src/dsv41/ds4_main.cpp:2511-2519,2553,2596-2599`）。

遅延方式の実効条件は `--vision-lazy` の指定ではなく、`--serve` が有効で、`--vision-resident` がなく、vision-only の `--encode-image` 実行でもないことです（`src/dsv41/ds4_main.cpp:2552-2553,2582,2619-2620`）。

## 実行時の動作

parser は `--vision-lazy` を認識すると `vision_lazy_asked = true` にしますが、この変数はその後参照されません。最終的な `o.vision_lazy` は `serve_mode && !vision_resident && !o.vision_only` から毎回設定されるため、フラグの有無は結果に影響しません（`src/dsv41/ds4_main.cpp:2506,2553,2619-2620`）。

遅延方式が有効なとき、モデル読み込み処理は `--reserve-mib` の予約量を vision tower の遅延化判定に渡します。既定予約量は 600 MiB です。GPU が統合型なら遅延化を要求せず、離散 GPU でも予約量が vision tower のデバイス側サイズと 192 MiB の余裕分以上でなければ tower は GPU に残ります（`src/dsv41/ds4_model.hpp:30,70-72`、`src/dsv41/ds4_model.cu:7732-7734`、`src/dsv41/ds4_vision.cuh:40-42,63`、`src/dsv41/ds4_vision.cu:397-405`）。遅延化された tower は重みをホストメモリに保持し、画像 encode 時に GPU メモリを確保します。serve は画像処理後に `vision_idle()` を呼び、遅延 tower の GPU 側領域を解放します（`src/dsv41/ds4_vision.cuh:13-15,52-55`、`src/dsv41/ds4_vision.cu:264-266,494-530`、`src/dsv41/ds4_main.cpp:1134`）。

`--vision-resident` は `vision_resident` を真にし、serve 時の遅延化を無効にします。`--vision off` は vision tower のロード自体を止めます。vision-only の `--encode-image` 経路も `o.vision_only` により遅延化対象外です（`src/dsv41/ds4_main.cpp:2551-2553,2619-2620`、`src/dsv41/ds4_model.cu:2814-2823`）。

## 適用条件と副作用

遅延化判定に失敗して tower が GPU に残る場合、serve はその理由を stderr に出します。理由は統合 GPU の共有メモリ、または離散 GPU で `--reserve-mib` が不足していることです（`src/dsv41/ds4_model.cu:7751-7753`）。遅延 tower が画像 encode 時に GPU メモリを確保できず、専門家用領域の貸し出しも成功しない場合は、空きメモリ取得を再試行した後に `vision: no graphics memory free for the picture tower ...; --vision-resident keeps it on the card` を返します（`src/dsv41/ds4_vision.cu:500-530`）。serve 側は画像処理失敗を stderr に出し、stdout に `ERR...` と `DONE... 0 ...` を出力して、その要求を失敗扱いにします（`src/dsv41/ds4_main.cpp:1134-1144`）。

ただし、いずれの挙動も `--vision-lazy` の指定によってオン・オフされるものではありません。GPU backend ごとの実動作や必要メモリ量はこのソース調査では実行検証していません。

## 出力とエラー

`--vision-lazy` 単独に固有のメッセージや validation error はありません。未知の option は `unknown option <値>` と usage を stderr に出し、終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:2596-2599`）。`strata-dsv41 --help` の usage には `--vision-lazy` が掲載されず、`--vision-resident` の説明で serve 時の遅延方式が既定とされています（`src/dsv41/ds4_main.cpp:115-123`）。同一 revision の既存 CLI バイナリによる `--help` は確認していません。

## 根拠

- parser と最終フラグ設定: `src/dsv41/ds4_main.cpp:2506,2551-2553,2582,2619-2620`
- usage と未知 option の失敗経路: `src/dsv41/ds4_main.cpp:115-123,2593-2599`
- option の既定値と `--vision` / `--vision-resident` の条件: `src/dsv41/ds4_model.hpp:26-30,68-72`、`src/dsv41/ds4_model.cu:2814-2823,7732-7754`
- 遅延判定、確保・解放、メモリ不足: `src/dsv41/ds4_vision.cuh:40-63`、`src/dsv41/ds4_vision.cu:264-266,397-405,494-530`
- serve の画像処理後の解放呼び出し: `src/dsv41/ds4_main.cpp:1134`

調査範囲は上記 Strata checkout のソースです。実行バイナリや各 backend 上での挙動は確認していません。
