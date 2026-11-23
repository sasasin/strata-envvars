# `strata update --force`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

エンジンの更新候補が以前のテスト起動に失敗した、または実モデルの初回起動に失敗して前のエンジンへ戻された場合に、その候補をもう一度試すよう要求する。通常の更新では失敗記録のある候補は保留され、`--force` を指定すると再試行の対象になる（`terminal/strata_cli/update_cmd.py:47-56,303-321`、`terminal/strata_control/updater.py:670-730,1484-1499`）。

## 使い方

```sh
strata update --force
```

再試行が成功すれば候補エンジンが次回起動から使われる。更新元や対象候補は通常の `strata update` と同じ feed・PC 向け選択で決まり、このフラグは特定バージョンを直接指定するものではない（`terminal/strata_cli/update_cmd.py:48-55,314-321`、`terminal/strata_control/updater.py:670-706,1622-1625`）。

## 値と既定値

引数値はなく、parser は `action="store_true"` で登録する。省略時は false、指定時は true となる。別名や値の validation は定義されていない（`terminal/strata_cli/update_cmd.py:47-56`）。

## 実行時の動作

`strata update` の実行時に parser の値が updater の `Context.force` に渡される（`terminal/strata_cli/update_cmd.py:303-321`）。`--check` と併用した場合は同じ候補選択判定に使われるため、失敗記録で通常は保留されるエンジンも「更新可能」として報告され得るが、`--check` 経路は feed の確認と表示で終了し、更新処理には進まない（`terminal/strata_cli/update_cmd.py:357-363`、`terminal/strata_control/updater.py:767-778`）。

更新時、updater は候補エンジンを選び、通常なら `failed-before` として止める状態でも `force` が true なら処理を続ける（`terminal/strata_control/updater.py:670-730,1484-1499`）。対象となる主な状態は次のとおり。

- 前回のテスト起動失敗が同じ候補の manifest に記録されている場合（GPU やメモリが使用中だった失敗は、この記録を作らない）。通常はその記録が24時間以内なら再試行を保留する。24時間を過ぎた記録や異なる manifest の候補は通常判定でも保留されない（`terminal/strata_control/updater.py:720-730,1557-1561,1904-1911`）。
- メモリ不足などで候補を十分にテストできず切り替えた後、実モデルの初回起動にも失敗して前のエンジンへ戻された場合。候補は `failed_unproven` に記録され、通常は再切り替えを保留する（`terminal/strata_control/updater.py:713-719,1812-1836`）。

前者では feed からエンジンを取得し、ステージングしてテスト起動する。テスト起動に失敗すると失敗理由・manifest・時刻を状態に記録し、現在のエンジンを維持する（`terminal/strata_control/updater.py:1500-1514,1538-1566`）。後者で候補エンジンがすでにローカルにあれば再ダウンロードせず、そのエンジンへ切り替える。未検証状態は維持され、実モデルの初回起動が再度失敗した場合は再び前のエンジンへ戻り得る（`terminal/strata_control/updater.py:1496-1535`）。

このフラグはエンジン候補の失敗保留に使われる。Control やアプリの更新可否を強制する処理には渡されない。GPU make の不一致を止める `make_guard` は候補選択の先頭で評価されるため、`--force` でその拒否を回避できない（`terminal/strata_control/updater.py:670-676,1484-1502,2087-2100`）。

## 適用条件と副作用

`strata update` がエンジン更新を実行するときに効果がある。`--no-engine` を同時指定するとエンジン更新ステップ自体が作られず、このフラグによる再試行も行われない（`terminal/strata_cli/update_cmd.py:61-69,367-368`、`terminal/strata_control/updater.py:2087-2100`）。

再試行は通常のエンジン更新と同じく feed の読み込み、必要な場合のダウンロード、検証・ステージング・テスト起動を伴う。成功時はエンジンの切り替えと状態・履歴の保存が行われ、旧エンジンは前のバージョンとして保持される（`terminal/strata_control/updater.py:1496-1514,1582-1625`）。候補をすでに保持している場合はダウンロードを行わず切り替える（`terminal/strata_control/updater.py:1496-1535`）。

## 出力とエラー

通常の人向け出力では更新結果を component ごとに表示する。`--output json` または `jsonl` では機械可読出力となる（`terminal/strata_cli/update_cmd.py:117-139,364-373,389-398`）。強制再試行のテスト起動が失敗した場合、エンジンはインストールされず現在のエンジンが維持され、失敗は既定の終了コード `6` で返る。失敗理由を含むエラーは人向けなら stderr、JSON 系なら error オブジェクトに出力される（`terminal/strata_control/updater.py:61-66,86-132,1557-1566`、`terminal/strata_cli/update_cmd.py:307-312,374-386`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における値なしフラグの登録。
- `terminal/strata_cli/update_cmd.py:303-321,357-373` — flag を `Context.force` に渡し、check または更新処理へ分岐する入口。
- `terminal/strata_control/updater.py:670-730` — エンジン候補選択、失敗記録の判定、`failed-before` への設定。
- `terminal/strata_control/updater.py:1484-1514,1538-1566` — 強制再試行の許可、取得・テスト起動、失敗時の記録。
- `terminal/strata_control/updater.py:1517-1535,1582-1625` — 既存候補への切り替えと成功時の状態保存。
- `terminal/strata_control/updater.py:1812-1836,1904-1911` — 未検証候補の自動ロールバック記録とテスト失敗記録の有効期間。
- `terminal/strata_control/updater.py:2087-2100` — engine / Control / app の更新ステップの分離。
