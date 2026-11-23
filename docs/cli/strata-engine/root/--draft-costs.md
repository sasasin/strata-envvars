# `strata --draft-costs`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（root、エンジン引数） |
| オプション | `--draft-costs` |
| 別名 | なし |
| 値 | 必須のファイルパス |

## 役割

`--serve` で動くエンジンのドラフト窓コスト表を保存・再利用するファイルを指定します。表が同じ machine/settings key に対応していれば、その測定値を使い、条件が変わった場合は実リクエストから表を学習します。オプションを省略した場合、表の読み書きは行いません（`engine/src/program/generate.cpp:936-940, 16343-16344`）。

## 使い方

新しいファイルパスを指定する例です。`./pack` はモデル pack、`./state/draft.costs` はこの実行用に用意した保存先を表します。

```sh
strata --serve --pack ./pack --tokens "1,2,3" --draft-costs ./state/draft.costs
```

## 値と既定値

- 値は `next()` で次の argv からそのまま取得します。値が省略されると stderr に `--draft-costs needs a value` を出して終了コード 2 で終了します。パスの形式、存在、書き込み可否は parser では検証しません（`engine/src/program/generate.cpp:3839-3842, 4208-4209`）。
- 既定値は空文字列（無効）です。空文字列を明示すると parser は受け取りますが、空でないことを条件とする実行時処理に入らないため、表は使われません（`engine/src/program/generate.cpp:936-940, 16343`）。
- 同じ指定を複数回すると `Options::draft_costs` への代入が後の値で置き換わります（`engine/src/program/generate.cpp:4208`）。

## 実行時の動作

- 表の処理は `--serve` の要求ループ内で、パスが空でなく、ドラフト方針がすでに固定されていないときに開始します。key にはエンジン version/backend、見えている GPU とその属性、該当 backend の driver/runtime version、適応設定、他のコマンドライン引数、`--draft-costs-key` の追加文字列が含まれます。引数中の表ファイル指定と key 追加指定自体は key から除外されます（`engine/src/program/generate.cpp:2286-2325, 16343-16345`）。
- key が一致する既存表は読み込んでドラフト方針へ設定します。該当する calibration 状態に応じて、表をすぐ使うか、live costs による判断を続けてから実リクエストで校正します。ファイルがない、読めない、形式不正、途中で切れている、または key が異なる場合は読み込み失敗扱いです。通常経路では live costs で要求を処理しながら表を作り、各窓サイズの実測がそろうか要求数上限に達した段階で利用・保存します（`engine/src/spec/draft_policy.cpp:263-367`, `engine/src/program/generate.cpp:16347-16398, 23192-23222`）。
- `--draft-costs-key TEXT` が指定されると追加 key として使われます。表のキーが GPU/driver/runtime、エンジン version、引数などの変化を含むため、別条件の表は再学習対象になります（`engine/src/program/generate.cpp:2286-2325, 16344`）。
- 表には CPU prompt share や PCIe share も保存される場合があります。読み込んだ表を適用するタイミングで、記録済みの share も該当する処理へ固定されます（`engine/include/strata/spec/draft_policy.hpp:108-145`, `engine/src/program/generate.cpp:16339-16341, 16377-16380`）。

## 適用条件と副作用

- parser は `--serve` との組み合わせを検証しませんが、表の読み書き・適用処理は serve 要求ループに置かれています。通常の単発 generate 実行で同じ表処理が行われることは、確認した実装からは読み取れません（`engine/src/program/generate.cpp:4208, 16343-16345`）。
- 表を書き込む際は親ディレクトリを作成し、指定ファイルの隣に `.tmp` を作ってから rename で置換します。既存の指定ファイルは置換されます（`engine/src/spec/draft_policy.cpp:370-429`）。
- 新規・不一致表は即時に固定されず、通常要求の測定から学習・校正します。記録内容の更新は要求終了時に行われ、後続要求に反映されます（`engine/src/program/generate.cpp:16353-16368, 23134-23222`）。

## 出力とエラー

- 起動時の表欠落・不一致・不正は読み込み理由として stderr に表示され、通常は処理を中断せず学習を始めます。表の学習開始・読込・校正・適用状況も stderr に出力されます（`engine/src/program/generate.cpp:16352-16403, 23134-23238`）。
- 書き込み時にディレクトリ作成、temporary file 書き込み、flush、rename のいずれかが失敗すると保存関数は失敗理由を返し、serve loop は「保存されなかった」旨を stderr に出します。これらの失敗を理由にその場で parser や serve loop を終了する経路は確認できません（`engine/src/spec/draft_policy.cpp:370-429`, `engine/src/program/generate.cpp:23160-23189, 23208-23212`）。
- 値がない場合は前述のとおり終了コード 2 です。未知の引数も stderr に `unknown argument` と usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:3839-3842, 4263-4268`）。

## 根拠

- `engine/src/program/generate.cpp:936-940, 4208-4209` — 設定値の既定値、parser 登録、および関連する `--draft-costs-key`。
- `engine/src/program/generate.cpp:2286-2325, 16343-16404` — key の構成、表の読み込み、学習・再利用の分岐と stderr 出力。
- `engine/src/program/generate.cpp:23134-23238` — 要求終了時の学習・校正・保存と後続要求への適用。
- `engine/include/strata/spec/draft_policy.hpp:108-145`, `engine/src/spec/draft_policy.cpp:263-429` — 表ファイル形式、読み込み検査、ディレクトリ作成・temporary file・置換。
- `engine/src/program/generate.cpp:3839-3842, 4263-4268` — 値の欠落と未知引数の失敗経路。
