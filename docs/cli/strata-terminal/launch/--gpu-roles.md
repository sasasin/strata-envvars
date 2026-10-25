# `--gpu-roles`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--gpu-roles` |
| 別名 | なし |
| 値 | GPU 番号と `main` / `helper` / `off` の組を並べたリスト |

## 役割

この起動で使う各 GPU の役割を指定します。Main はモデル分割の最後の段を実行し、Helper はモデルの一部を保持し、Off は Strata がそのカードを使わない指定です。Main はエンジンへ渡す GPU 順の最後になります。

## 使い方

```sh
strata launch --model q2_0 --gpu-roles 1=main,0=helper --no-tui
```

指定した GPU 番号は、この Strata build が利用できる GPU の番号です。番号は `nvidia-smi` と同じ番号体系です。値には `番号=役割` のほか `番号:役割` も使え、項目はカンマまたはセミコロンで区切れます。空白と役割の大文字・小文字は正規化されます。例: `1:MAIN; 0:helper`。

## 値と既定値

- 値は必須で、少なくとも1カードを記述します。GPU 番号は数字、役割は `main`、`helper`、`off` のいずれかです。
- 同じ GPU の重複指定と Main の複数指定はエラーです。Main を書かない値は受理され、後段で有効なカードのうち1枚が Main に補完されます。
- 1件も解釈できない空値、不正な区切り、負数などの非数字番号、未知の役割はエラーです。末尾や連続区切りの空項目は読み飛ばされます。
- `--gpu-roles` を省略した場合、このオプションによる役割指定はありません。preset の既存選択や通常のカード選択が使われます。

## 実行時の動作

`--gpu` と同時に指定すると拒否されます。preset を読み込んでいる場合、明示した `--gpu-roles` はその起動の役割を置き換えます。`--gpu` を指定した場合は preset の役割が消えます。`--save-preset` も付ければ、その起動設定を preset として保存できます。

CLI は値を役割辞書に変換し、現在の build で認識するカード一覧に対して、指定していないカードを Off として補います。複数カードが on で Main が未指定なら、共通の正規化処理がカード情報から Main を選びます。モデル準備時、runner は役割を setup 呼び出しの `--gpu-roles` 引数として渡します。モデル準備後の launch 設定ファイルには役割と旧形式互換の GPU 順が書き込まれます。

サーバーは保存された役割から Helper を先、Main を最後にした GPU リストを作り、Off のカードを除外します。役割指定が有効な場合、通常の速度順による再並べ替えは行いません。エンジンのログにはカード役割が表示されます。

## 適用条件と副作用

- build の利用可能 vendor を判定できる場合、指定されたカード番号が使えるカード一覧にないとエラーになります。異なる GPU vendor のカードを混ぜて指定することもできません。
- 全カードを Off にする値は CLI parser では受理されます。CUDA / HIP / SYCL engine は GPU なしでは起動できず、サーバーは理由を1行表示して停止します。CPU 実行可能な engine（`cpu` / `metal` backend、または macOS）では CPU のみの性能低下メッセージを出して続行します。
- 通常の `strata launch` はモデルや engine の準備、launch 設定の書き込み、サーバー起動を行います。`--plan` を付けた場合は計画を表示して終了し、変更を行わない経路です。
- hardware 情報を使った役割変換で例外が発生した場合、カード選択 helper は launch を止めず `None` を返します。その場合に最終的に使われる設定は、既存設定など後続の通常処理に依存します。

## 出力とエラー

- 値の形式エラー、および `--gpu` との併用エラーは `ValueError` となり、通常出力では標準エラーに `strata: ...` を表示して終了コード `2` になります。`--output json` ではエラー情報を JSON で出力します。
- 未知のカード番号は launch 設定の確認時にエラーとして返され、起動処理の前に終了コード `2` になります。
- 全カード Off の場合、CUDA / HIP / SYCL の拒否はサーバー側の `SystemExit` 経路です。確認したソースではこの経路のプロセス終了コードまでは特定できません。

## 根拠

- `strata_cli/launch/cmd.py:108-110` — parser 定義とヘルプ文。`strata_cli/launch/cmd.py:236-247` — `--gpu` との排他、値の解析、preset 設定への反映。
- `strata_control/gpu_roles.py:21-27,138-152` — 役割名、正規化、Main の補完規則。`strata_control/gpu_roles.py:195-215` — engine 順と設定への互換ミラー。`strata_control/gpu_roles.py:218-244` — 値の構文・重複・Main 数の検査。
- `strata_cli/launch/cmd.py:376-404,720-725` — build が使えるカード番号の確認とエラー時の終了。`strata_cli/launch/cmd.py:636-641,832-837` — エラー出力形式と終了コード。
- `strata_cli/launch/runner.py:341-368,738-759,777-794,1235-1243` — 役割からカード設定を作る処理、setup への引き渡し、保存済み選択の引継ぎ、launch 設定の書き込み。
- `strata_control/gpu_roles.py:1-9,203-215` — Main / Helper / Off の意味と Main を最後にする規則。`serve/server.py:2913-2920,2941-2957,3346-3358` — サーバー側の GPU リスト化、全 Off の分岐、役割指定時の順序保持。
- `docs/MULTI_GPU.md:44-67,69-89` — 利用者向けの役割説明と設定例。実装根拠ではなく補助資料として参照。
