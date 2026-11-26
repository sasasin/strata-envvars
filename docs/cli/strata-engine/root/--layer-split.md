# `strata --layer-split`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、トップレベル引数） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | `auto`、または後段 GPU ごとの層開始番号を昇順で並べた `K[,K2...]` |

## 役割

`--serve` モードでモデルの層を複数 GPU の連続した範囲に分けます。`K` は GPU ごとの層数ではなく、各後段 GPU が担当し始める層番号です。`auto` は読み込んだモデル、各 GPU の空き VRAM、セッションと expert cache の見積もりなどから配置を探索します。分割を指定しない場合はこの経路に入らず、通常の単一 GPU 実行になります（parser の格納先と分岐: `engine/src/program/generate.cpp:1070-1073, 4065, 4786-4805`）。

## 使い方

```sh
# GPU へ自動配置して server モードで起動
strata --serve --pack /path/to/model.strata --layer-split auto

# CUDA0 と次の GPU の境界を層 24 に固定
strata --serve --pack /path/to/model.strata --layer-split 24

# 4 GPU の境界を層 24、36、42 に固定
strata --serve --pack /path/to/model.strata --layer-split 24,36,42

# 後段 GPU を ordinal 2 に明示（境界と GPU 数は一致させる）
strata --serve --pack /path/to/model.strata --layer-split 24 --split-device 2
```

## 値と既定値

- 値は必須です。値を省略すると parser が `--layer-split needs a value` を stderr に出し、終了コード `2` で終了します。parser は値を `Options::layer_split` に文字列として格納し、同じオプションを複数回指定した場合は後の指定が上書きします（`engine/src/program/generate.cpp:3844-3848, 4065`）。
- `auto` は完全一致で認識されます。それ以外は10進数字のみのカンマ区切りです。空要素、空白、符号、小数は受理されません（`engine/src/program/generate.cpp:4791-4804`）。
- 明示する各 `K` は `2` 以上、昇順で重複不可です。境界の個数と後段 GPU 数は一致し、最終境界はモデルの最終層番号未満でなければなりません。違反すると stderr にエラーを出して終了コード `2` になります（`engine/src/program/generate.cpp:4841-4853, 7593-7598`）。
- `--layer-split` を省略したときの値は空文字列で、分割を有効にしません（`engine/src/program/generate.cpp:1070-1073`）。

## 実行時の動作

- オプションを使うには `--serve` が必要です。手動指定では、`--split-device` を省略すると CUDA ordinal 1 から必要数を順に選びます。`--split-device` を指定する場合は、カンマ区切りの異なる ordinal を指定し、各 ordinal は 1 以上かつ可視 GPU 数未満でなければなりません。明示値 `K` が1個だけの場合に限り、`--split-device 0` で同じ GPU 上の二段を選べます（`engine/src/program/generate.cpp:4786-4809, 4841-4853`）。
- `auto` では後段 GPU を既定で ordinal 1 から候補にし、GPU の空き容量・モデル層・セッション容量・expert profile/cache などから配置を探索します。探索結果の境界と予測値を stderr に表示します。可視 GPU が1台なら「分割なし」と表示してオプションを解除し、単一 GPU 経路へ進みます（`engine/src/program/generate.cpp:4803-4808, 4836-4839, 6949-6970, 7501-7510`）。
- 境界 `K1,K2,...` から段ごとの範囲 `[0,K1)`, `[K1,K2)`, … が設定され、後段 GPU にはその範囲の層が割り当てられます。エンジンは分割 GPU と境界を stderr に記録します（`engine/src/program/generate.cpp:4774-4780, 4971-4973, 7666-7669`）。
- `--split-skip-if-fits` は `auto` のときだけ作用します。profile 済み expert pair、セッション、drafter、reserve が CUDA0 に収まると分割を解除し、収まらないか profile がない場合は分割を維持します（`engine/src/program/generate.cpp:6450-6491`）。

## 適用条件と副作用

- `--serve` なしでは無効値として拒否されます。`STRATA_PRIMARY_DEVICE` が0以外の場合も、分割はまだサポートされないとして終了コード `2` で拒否されます（`engine/src/program/generate.cpp:4804, 4856-4864`）。
- `--peer-device` とは併用できず、stderr に競合を示して終了コード `2` になります。`--gpu-only-full` または `--gpu-stages` も複数 GPU 分割時には拒否されます。これらは単一セッションで全モデルを再生するためです（`engine/src/program/generate.cpp:5284-5290, 5301-5307`）。
- `--expert-cache-remote` と併用する場合、分割段に使わない追加 GPU が必要です。空き GPU がなければ起動前に終了コード `2` で失敗します。コードコメントでは、層をまたぐ control vector、remote helper cache、prompt path への cache slot 貸し出しは分割時に未対応とされています（`engine/src/program/generate.cpp:4774-4780, 4958-4968`）。
- `auto` で探索可能な配置がない場合は stderr に理由を出し、終了コード `2` で失敗します。自動配置ではメモリ不足に応じて後段 GPU を除外する経路や、KV window を縮めて再探索する経路もあります。手動配置では境界を自動調整しません（`engine/src/program/generate.cpp:4817-4835, 7466-7504`）。
- 分割は GPU 上に複数段を構成して、それぞれの層範囲の重み・セッションを割り当てるため、GPU メモリを使用し、GPU 間の引き渡しを伴います。`auto` は起動時の空き容量等を見て決定されます（`engine/src/program/generate.cpp:4768-4780, 6959-6970, 7666-7683`）。

## 出力とエラー

値不足、形式・境界・GPU 数の不一致、`--serve` の欠落、未対応の組み合わせは stderr に診断を出して終了コード `2` になります。自動配置不能も同じ終了コードです。正常な分割では分割 GPU と境界を stderr に表示します（`engine/src/program/generate.cpp:3844-3848, 4848-4853, 4971-4973, 7501-7504`）。

## 根拠

- `engine/src/program/generate.cpp:1070-1073, 4065` — option 値の格納と関連する `--split-device` 設定。
- `engine/src/program/generate.cpp:4786-4853` — `--serve` 条件、値の解析、既定 GPU 選択、手動境界・GPU ordinal の validation とエラー。
- `engine/src/program/generate.cpp:6450-6491, 6949-6970, 7501-7510` — `--split-skip-if-fits` と自動配置探索・失敗経路。
- `engine/src/program/generate.cpp:7666-7683` — 決定した境界を各 GPU stage の層範囲と重み読み込みへ反映。
- `docs/cli/README.md:1036-1112` — `strata-engine` のトップレベル引数スコープと対象リンク。
- `docs/cli/000_cli_tools.md:7-10` — `strata-engine` の parser 所在と `root/` スコープ。

調査時点で checkout は `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`、作業状態は `main...origin/main` で、未コミット変更の表示はありません。GPU backend ごとの実行時差や全失敗時の stderr は網羅していません。上記は共通 parser と CUDA 配置経路でソース確認できた範囲です。
