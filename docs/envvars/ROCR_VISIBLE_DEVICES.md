# `ROCR_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata の Python 側で、AMD GPU の環境可視性を読み取り、GPU の一覧や起動計画から隠れているカードを除外する。また、HIP エンジンの起動時に Strata が別途 GPU を自動選択するかどうか、および更新後のエンジン起動確認で GPU を自動絞り込みするかどうかを決める。Strata のエンジン C++/HIP 実装がこの名前を直接読む箇所は確認できず、GPU runtime 自身の解釈は本書の対象外である。

`strata_control.gpu_roles.env_visible` は環境値を AMD 用の可視カード一覧に変換し、`visible_cards` と `strata_control.split_engine._named_or_visible` がそれをカード一覧・分割起動計画に適用する。サーバーでは `child_env` が親環境を子プロセス用辞書にコピーし、`hip_auto_devices` がこの変数の有無を見て自動選択プローブを抑止する。更新確認では `updater.hip_test_cards` が同じ有無判定を行う（`terminal/strata_control/gpu_roles.py:466-518`、`terminal/strata_control/split_engine.py:396-405`、`terminal/serve/server.py:3832-3860,3870-3925`、`terminal/strata_control/updater.py:961-985,1013-1027`）。

## 値と判定

| 用途 | 未設定 | 有効になる値（例） | 無効・特殊な値（例） |
|---|---|---|---|
| AMD GPU の一覧・起動計画に使う可視カードの対応付け | 制限なしとして `None`。他に HIP 側の指定があればそちらを読む | カンマ区切りの整数 ordinal。例: `0`、`1,0`。前後空白と各要素の前後空白は除去される | 空文字・空白だけは空リスト `[]`（可視カードなし）。`-1` など範囲外の整数はその要素で処理を止め、それまでの要素を返す。`GPU-...`、`+1`、`0anything`、空要素を含む `0,` など整数でない要素は `None` となり、Strata は一覧を絞り込めない。大文字小文字は関係しない。ただし `--1` は文字検査を通った後の `int()` で `ValueError` になる |
| HIP サーバー起動時の自動 GPU 選択抑止 | 未設定なら、この変数による抑止なし | 空でない任意の文字列。例: `0`、`GPU-...`、空白 | 空文字は抑止しない。値の数値変換・書式検査はしない |
| 更新後の HIP エンジン起動確認時の自動 GPU 絞り込み抑止 | 未設定なら、この変数による抑止なし | 空でない任意の文字列。例: `0`、`GPU-...`、空白 | 空文字は抑止しない。値の数値変換・書式検査はしない |

一覧・計画経路の整数解釈では、値の各要素は `indexes` 配列内の ordinal として扱われる。ordinal が配列範囲を越えた場合はエラーにせず、その時点でリスト処理を止める。`ROCR_VISIBLE_DEVICES` を先に適用し、設定されていれば `HIP_VISIBLE_DEVICES` をその結果に対してさらに適用する。形式不正値は通常「可視カードなし」ではなく「対応付け不能」になり、その経路ではフィルターを適用しない。ただし `--1` のようにハイフンが複数ある要素は `.lstrip("-").isdigit()` を通過して `int()` で例外になる。launch ロール表示側は例外を握りつぶして表示行を省くが、分割計画側にはこの変換例外を捕捉する処理がない（`terminal/strata_control/gpu_roles.py:466-502,513-518`、`terminal/strata_cli/launch/cmd.py:429-443`、`terminal/strata_control/split_engine.py:396-405`）。

## 有効になる条件

- 一覧・計画の可視カード判定は vendor が `amd` の場合にだけ `ROCR_VISIBLE_DEVICES` を参照する。Intel/NVIDIA や vendor 不明の場合、この名前はその判定に使われない（`terminal/strata_control/gpu_roles.py:485-510`）。
- `strata launch` のロール表示は GPU またはロールを指定したときにカード一覧を環境で絞るが、明示的に指定された GPU は隠れていても `keep` として残す（`terminal/strata_cli/launch/cmd.py:425-441`、`terminal/strata_control/gpu_roles.py:513-518`）。
- 分割起動計画ではカードを明示指定していないときだけ環境可視性でカードを絞る。明示された index がある場合はそのカードだけを使い、この環境値のフィルターを通さない（`terminal/strata_control/split_engine.py:396-405`）。
- HIP サーバーの追加自動選択は、backend が `hip`、GPU の明示指定なし、全 GPU Off ではない、`hip_ordinal` が空、かつ `HIP_VISIBLE_DEVICES` と `ROCR_VISIBLE_DEVICES` の両方が空の場合にだけ試みる。したがって `ROCR_VISIBLE_DEVICES` は `0` や UUID 形式でも、空でなければこのプローブを抑止する（`terminal/serve/server.py:3832-3848`）。
- 更新後の起動確認での追加絞り込みは、コンポーネント backend が `hip` で始まり、かつ `HIP_VISIBLE_DEVICES` と `ROCR_VISIBLE_DEVICES` がどちらも空の場合にだけ試みる（`terminal/strata_control/updater.py:961-985`）。

## 実行時の詳細

`gpu_roles.env_visible` は呼び出し時に `environ` 引数がなければ `os.environ` を参照する。値をキャッシュしない。`visible_cards` は GPU 一覧をフィルターし、明示指定されたカードは保持する。分割起動計画の `_named_or_visible` は、カードが明示されない場合にこの関数を呼び、返された可視 index にあるカードだけを候補にする（`terminal/strata_control/gpu_roles.py:485-518`、`terminal/strata_control/split_engine.py:396-405`）。

サーバーの `child_env` は呼び出し時の `os.environ` を辞書にコピーするので、元の `ROCR_VISIBLE_DEVICES` は通常そのまま子エンジン環境に含まれる。GPU 全 Off の設定では Strata は `CUDA_VISIBLE_DEVICES` と `HIP_VISIBLE_DEVICES` を空にし、明示 GPU 選択時は backend に応じて `HIP_VISIBLE_DEVICES` または `CUDA_VISIBLE_DEVICES` を設定する。いずれもこの処理自体は `ROCR_VISIBLE_DEVICES` を削除しない。HIP backend ではその後 `hip_auto_devices` が非空の ROCR/HIP 値を見つけると probe を行わず、設定が空なら隣接する `strata-device --list-devices` を最大60秒実行して選択候補を調べる（`terminal/serve/server.py:3870-3891,3917-3925,3832-3860`）。

更新時の起動確認は `os.environ` のコピーを使い、動的ライブラリ検索パスを加えた後に `hip_test_cards` を呼ぶ。ROCR/HIP のどちらも空でなく追加絞り込み対象が得られた場合だけ、確認用子プロセスの `HIP_VISIBLE_DEVICES` を設定して `--version` を実行する。ユーザー環境に非空の `ROCR_VISIBLE_DEVICES` がある場合は追加プローブをせず、コピーされた環境を引き継いで確認する（`terminal/strata_control/updater.py:961-985,1013-1027`）。

## ログと測定値

この変数を読み取ったこと自体を知らせる Strata のログはない。HIP サーバーの自動選択プローブがカードを選んだ場合は `[strata] automatic GPU choice: GPU ...` で始まる行を出すが、ROCR 値が非空でプローブを抑止した場合にはこの選択ログは出ない（`terminal/serve/server.py:3832-3860`）。更新確認では、`--version` が失敗した際にエンジン出力などを理由とログに保存する経路があるが、これはこの環境変数専用の警告ではない（`terminal/strata_control/updater.py:1024-1056`）。性能測定値は該当しない。

## 根拠

- `terminal/strata_control/gpu_roles.py:466-518` — 値の ordinal 解釈、AMD での ROCR 優先読み取り、可視カードへの適用。
- `terminal/strata_control/split_engine.py:396-405` — 明示 index がない分割計画での可視カード絞り込み。
- `terminal/strata_cli/launch/cmd.py:425-441` — launch の GPU ロール行での一覧利用と明示 GPU 保持。
- `terminal/serve/server.py:3832-3860,3870-3925` — HIP 起動時の抑止条件、親環境のコピー、選択プローブと child env の調整。
- `terminal/strata_control/updater.py:961-985,1013-1056` — 更新確認時の抑止、子環境の設定、失敗の観測経路。
