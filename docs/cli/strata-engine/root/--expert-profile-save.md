# `--expert-profile-save`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--expert-profile-save` |
| 別名 | なし |
| 値 | 保存先ファイルのパス（文字列） |

## 役割

`--serve` 実行中に adaptive tier が学習した expert の順位を、次回起動時に `--expert-profile` で読み込めるプロファイルとして保存します。保存順は現在 VRAM に resident な expert を先頭に置き、その後は実行開始から数えた routing の頻度を基準にします（`src/program/generate.cpp:988-993`、`include/strata/core/expert_cache.hpp:57-71`）。

## 使い方

```sh
engine/strata --serve --pack /path/to/model-pack \
  --expert-profile /path/to/base-profile.bin \
  --expert-profile-save /path/to/learned-profile.bin
```

これはエンジンのネイティブ引数例です。`--expert-profile-save` 自体は parser で受理されますが、保存処理は `--serve` の実行経路内にあります（`src/program/generate.cpp:2416-2425, 2748-2753`、保存処理は `src/program/generate.cpp:10888-10906, 15685`）。

## 値と既定値

- 値は次の argv 要素をそのまま保存先パスとして受け取ります。値を省略すると stderr に `<option> needs a value` を出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2421, 2750`）。空文字列は parser では拒否されず、保存機能を無効にする値として扱われます（`src/program/generate.cpp:588-592, 10070-10078`）。
- 指定しない場合の値は空文字列で、profile の heat 計数・ファイル書き込みを行いません（`src/program/generate.cpp:588-592, 10890-10892`）。
- このオプションについて、パスの事前検証、拡張子検証、重複指定検証はありません。複数回指定した場合は parser が同じ文字列フィールドへ順に代入するため、最後の値が残ります（`src/program/generate.cpp:2416-2421, 2750`）。
- 相対パスはプロセスの作業ディレクトリを基準にファイル API へ渡されます。エンジン設定を介して起動する `serve` 側では、相対パスを config の `cwd` 基準に解決する実装です（`src/core/expert_cache.cpp:193-205`、`serve/server.py:3197-3216`）。

## 実行時の動作

保存は `--serve` 経路の起動時に、`--expert-profile-save` が空でなく、全 expert が resident ではない場合に準備されます。routing usage または host residency table が使えない場合、stderr に adaptive tier（`--adapt-every` と `--adapt-swaps` が正値）および `--expert-profile` が必要で保存されない旨を警告します。両方が有効なら、routing の累積用 `heat` を初期化します（`src/program/generate.cpp:10070-10080`）。全 expert が resident の場合はこの保存機能の heat を初期化しません。

各 adaptive round では routing usage を heat に足し、通常の adaptive tier と同様に usage を decay します（`src/program/generate.cpp:10446-10460, 10735-10745`）。現在の residency と heat から全 `(layer, expert)` ペアを順位付けし、開始時に読み込まれた profile を同率時の prior として使います。優先順位は resident、heat の降順、prior の順位、最後に index です。したがって、この出力を次回の `--expert-profile` に使うと、実行終了時点の cache residency が先頭に反映されます（`src/program/generate.cpp:4455-4461, 10890-10900`、`src/core/expert_cache.cpp:143-169`）。

## 適用条件と副作用

- 意図された用途は `--serve` です。更新間隔の既定値は関連オプション `--expert-profile-save-every` が設定する10分で、経過後、次のリクエストを処理する前に保存します。`0` 以下なら定期保存条件を満たさず、終了時保存だけになります。更新間隔の parser は `std::atof` で、明示値の範囲検証は確認できません（`src/program/generate.cpp:591-592, 2750-2753, 12016-12020`）。
- QUIT または標準入力終了で server loop を抜けた後にも保存を試みます（`src/program/generate.cpp:15685`）。通常の非-serving生成経路にはこの保存呼び出しがありません。
- 出力は `STRP` 形式の version 1 で、モデルの layer/expert 数、ranked pair 群、rank table を含みます。`<path>.tmp` に書き、完了後 rename で最終パスへ置き換えるため、既存の保存先ファイルは更新時に置換されます（`include/strata/core/expert_cache.hpp:68-71`、`src/core/expert_cache.cpp:172-211`）。保存先と `.tmp` を同時に他の処理で使わないでください。
- 既存の `--expert-profile` と同じパスを保存先にすると、起動時に読んだ内容を開始時の prior として保持したうえで、保存時にそのファイルを置換します。これは実装上可能ですが、バックアップは作られません（`src/program/generate.cpp:4458-4461`、`src/core/expert_cache.cpp:193-205`）。
- Engine が直接受け取った `--expert-profile-save-every` の負値は定期保存を無効化します。config 経由では `serve/server.py` が `expert_profile_save_every` を数値かつ非負の場合だけ engine 引数に追加します（`src/program/generate.cpp:12016-12020`、`serve/server.py:3207-3209`）。

## 出力とエラー

- 保存成功時は stderr に `strata serve: expert profile saved to <path> (periodic|exit)` を出します。失敗時は `strata serve: the expert profile was not saved: <理由>` を出します（`src/program/generate.cpp:10898-10905`）。
- 親ディレクトリがない、権限がない、または一時ファイル・最終ファイルへの書き込み/rename ができない場合は保存関数が失敗し、可能なら `.tmp` を削除します（`src/core/expert_cache.cpp:193-209`）。この失敗は `save_profile` からエラー表示されますが、当該関数は戻り値を返さず、ここで終了コードを失敗に変更しません（`src/program/generate.cpp:10890-10906, 15685-15693`）。
- モデルの layout が形式の範囲（layer/expert 数が1〜65535）に収まらない場合や順位に範囲外 pair がある場合も保存関数が失敗します（`src/core/expert_cache.cpp:172-188`）。
- `--expert-profile-save` が指定されたものの adaptive tier の準備条件を満たさない場合、起動時警告を出し、`heat` が空のままなので周期・終了時どちらの保存も行いません（`src/program/generate.cpp:10073-10078, 10890-10892`）。

## 根拠

- 索引上の位置と scope: `docs/cli/README.md:1128-1134, 1178-1180`（strata-envvars 側）。
- parser、値欠落時の扱い、既定値: `src/program/generate.cpp:588-592, 2416-2421, 2748-2753`。
- serving 時の適用条件と routing 計数: `src/program/generate.cpp:10070-10080, 10446-10460, 10735-10745`。
- 順位付けと書き込み形式・失敗経路: `include/strata/core/expert_cache.hpp:57-73`, `src/core/expert_cache.cpp:143-211`。
- 保存タイミング、ログ、終了時呼び出し: `src/program/generate.cpp:10888-10906, 12016-12020, 15685-15693`。
- config 経由の引数補完と相対パス解決: `serve/server.py:3197-3216`。

調査では同一 revision の既存 CLI `--help`、Release artifact、GPU 実行は利用していません。記述は上記 checkout の parser と処理経路に基づきます。
