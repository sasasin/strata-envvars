# `strata --cvec-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジンの root 引数） |
| オプション | `--cvec-dir` |
| 別名 | なし |
| 値 | `per-layer` または `single:L`。`L` は制御ベクトルの層番号 |

## 役割

制御ベクトルを `--cvec-mode project` で使うとき、各適用層にその層自身の方向を使うか（`per-layer`）、指定層 `L` の方向を適用層すべてで共用するか（`single:L`）を選びます。制御ベクトルファイルを指定しない場合、または `--cvec-mode add` の場合、この指定は方向選択に反映されません。

## 使い方

```sh
# 層 4 の方向を、指定した層範囲に共通して使う（CVEC.gguf と PACK は手元の入力に置き換える）
strata --pack PACK --tokens "1,2,3" \
  --control-vector-scaled CVEC.gguf:1.0 --control-vector-layer-range 4 44 \
  --cvec-mode project --cvec-dir single:4
```

## 値と既定値

- `per-layer` は内部値を `-1` にし、project モードで適用先の各層自身の方向を使います。既定値も内部値 `-1`（per-layer 相当）です。`--cvec-dir` の複数回指定は、引数処理中の最後の値が残ります（`engine/src/program/generate.cpp:1205,4190-4194`）。
- `single:L` は `single:` の後ろを `atoi` で整数変換します。パーサー段階では数値全体の形式や符号・範囲を厳密には検査せず、`single:` という接頭辞だけを確認します。したがって数値でない接尾辞は `0` として扱われ、数値の後ろに余分な文字があっても `atoi` が読める先頭部分が使われます（`engine/src/program/generate.cpp:4190-4194`）。
- ベクトル読込時、project モードの `single:L` はベクトルにその層の方向が存在する必要があります。層 0 の方向は読込対象外のため指定できません。モデルの層数を超える番号や、該当方向のない番号も読込エラーになります（`engine/src/program/generate.cpp:2760-2764,2788-2791`）。
- `single:` の後ろが負数なら内部値が負になり、project モードでも per-layer と同じ分岐になります。これは専用の拒否ではなく、実装上 `single >= 0` の場合だけ単一層として扱うためです（`engine/src/program/generate.cpp:2788-2797`）。

## 実行時の動作

`--cvec-dir` は方向選択を `Options::cvec_single` に保存します。制御ベクトルファイルが一つ以上指定されたときだけ読込処理が呼ばれ、`--cvec-mode project` なら `single:L` の層を全適用層の参照元にし、`per-layer` なら適用層ごとに同番号の方向を参照します。選ばれた方向から層ごとの方向・スケール表を作り、GPU 用の制御ベクトル表としてアップロードします（`engine/src/program/generate.cpp:2788-2813,6143-6150`）。

`--cvec-mode add` では `cvec_single` を使わず、`per-layer` と同じく各層の方向を使います。そのため `--cvec-dir single:L` を指定しても add モードの方向は切り替わりません（`engine/src/program/generate.cpp:2788-2809`）。GPU 側では層ごとの表を参照して residual stream にベクトルを適用します（`engine/src/kernels/cuda/cvec.cu:52-56,86-93,162-171`）。

## 適用条件と副作用

- `--cvec-dir` の値はベクトルが未指定でも `per-layer` / `single:` の形式検査を受けますが、層の存在確認は制御ベクトル読込処理内でしか行われません。ファイル未指定ではその処理が呼ばれないため、認識された値でも実行上は効果がありません（`engine/src/program/generate.cpp:4190-4194,6143-6150`）。
- `--cvec-mode project` 以外では `single:L` を単一方向として解釈しません。`--cvec-mode` が省略された場合の mode は add（内部値 `1`）です（`engine/src/program/generate.cpp:1204-1205,2788`）。
- 値の指定による出力ファイルの生成や書換えは確認できません。ベクトル読込後は GPU テーブルへのアップロードが行われます（`engine/src/program/generate.cpp:2813`）。
- この調査では `engine/src/program/generate.cpp` の parser とその CUDA 側の利用を追跡しました。SYCL 用ソースにも同じ値の parser とベクトル選択処理がありますが、バックエンドごとの実行環境差・GPU 上の結果は実行して確認していません（`engine/sycl/src/program/generate.cpp:1577-1604,2148-2158`）。

## 出力とエラー

- 値が欠けていると `--cvec-dir needs a value` を stderr に出し、終了コード `2` で終了します。`per-layer` / `single:` 以外は `--cvec-dir: per-layer or single:L, got '…'` を stderr に出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:3844-3846,4190-4194`）。
- ベクトルを読み込む project モードで `single:L` に該当方向がない場合は、`strata generate: control vector: --cvec-dir single:L: the vector has no direction for that layer` を stderr に出して終了コード `2` になります（`engine/src/program/generate.cpp:2788-2791,6145-6150`）。
- 指定層の合成方向がゼロで適用層が一つも steer されない場合も、読込処理は「control vector has no direction in layers …」として失敗し、呼び出し元が stderr に出して終了コード `2` を返します。アップロード失敗も同じ呼び出し元経由でエラー表示・終了コード `2` になります（`engine/src/program/generate.cpp:2800-2813,6145-6150`）。
- 読込に成功すると stderr に mode、`dir` の選択種別、適用層範囲、方向を適用した層数を出力します（`engine/src/program/generate.cpp:2825-2829`）。
- ソースの `usage()` 表示は `strata generate ...` と記しますが、root parser は引数を直接処理し、`generate` を未知引数として拒否します。例では parser に沿って `strata --pack ...` の形を示しました（`engine/src/program/generate.cpp:1208-1211,3842-3850,4268-4274`）。

## 根拠

- `engine/src/program/generate.cpp:1199-1205,1370-1374` — 制御ベクトル設定の既定値と help 表示上の値形式。
- `engine/src/program/generate.cpp:3842-3846,4184-4195,4268-4274` — root 引数 parser、値取得、形式判定、未知引数の失敗。
- `engine/src/program/generate.cpp:2739-2744,2760-2784,2786-2813,2825-2829,6143-6150` — ベクトル層の選択・検証、GPU 表アップロード、診断出力、失敗終了。
- `engine/src/kernels/cuda/cvec.cu:46-56,86-93,162-171` — 層ごとの方向表の参照と residual stream への適用。
- `engine/sycl/src/program/generate.cpp:1577-1604,2148-2158` — SYCL 用 parser と層選択処理の対応箇所。
