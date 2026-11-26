# `setup.sh` / `START-HERE.bat` `--vram-reserve-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.sh` / `START-HERE.bat`（`terminal/setup.py`） |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | `N`（MiB 単位の整数、0 以上） |

## 役割

モデル用 GPU メモリのうち、他のプログラム向けに空けておく量をセットアップ時または既存モデルの起動時に指定します。モデルの実行設定へエンジン引数として保存され、その分だけエキスパートキャッシュ等に割り当てられる量が小さくなります。通常のエンジン既定値は 700 MiB ですが、この値を指定するとその設定を明示的に上書きします。`terminal/setup.py` は `setup.sh` と `START-HERE.bat` から呼び出されます（`setup.sh:6-17,81`、`START-HERE.bat:8-17,49-65`）。

## 使い方

```sh
# モデルのセットアップ時に 1 GiB を他のプログラム向けに確保する
./setup.sh --setup --model Q2_0 --vram-reserve-mib 1024

# 既にセットアップ済みのモデルを起動し、予約量を 1.5 GiB に更新する
./setup.sh --vram-reserve-mib 1536
```

Windows では同じ引数を `START-HERE.bat` に渡します。コマンドライン引数の値は `argparse` の `type=int` で変換され、`--vram-reserve-mib=1024` 形式も parser の標準構文として受理されます（`terminal/setup.py:11572-11574`）。

## 値と既定値

- `N` は整数です。省略時は `None` で、通常セットアップではこのオプションによる明示設定を追加しません。エンジン側の既定値は 700 MiB と parser の説明に記載されています（`terminal/setup.py:11572-11574`）。
- 0 は受理されます。負数は `ap.error(...)` で拒否され、例示された使用法を含むエラーになります（`terminal/setup.py:11643-11644`）。非整数は `argparse` の型変換で拒否されます（同 `11572`）。
- 同じオプションを複数指定した場合の `argparse` の値が使われます。setup.py 側で重複指定を別途検出する処理は確認できませんでした。

## 実行時の動作

通常のモデルセットアップでは、`strata_control/setup_config.py` が実行設定の `args` に `--vram-reserve-mib N` を追加します。画像読み取りを GPU で行う構成が既に持つ予約量があれば、その値を指定値で置き換えます。画像エンコーダーが必要とする量より小さい値を指定した場合は、VRAM 不足の可能性を警告して指定値を維持します。設定作成時には「指定 MiB を他プログラム向けに空け、エキスパートキャッシュがその分少なくなる」と表示します（`terminal/strata_control/setup_config.py:350-368`）。

既存モデルを `--setup` なしで起動する経路では、値をそのモデルの設定 JSON の `args` に追加または既存値と置換し、`user_args` にも記録して JSON を書き込みます。その後、サーバー起動へ進みます。これにより後続のセットアップでも利用者が指定した値として引き継がれます（`terminal/setup.py:8577-8589`、通常起動から渡す箇所 `11761-11775`、再セットアップ時の引き継ぎ `7626-7629,7632-7657`）。

通常のセットアップが既存 JSON を変更する場合、更新前の内容を `.bak` にコピーしてから新しい設定を書きます。バックアップ作成に失敗した場合は警告し、設定自体の書き込みは続けます（`terminal/setup.py:7736-7749`）。

## 適用条件と副作用

- オプションはトップレベル parser にあります。通常のモデル設定ではエンジン引数として保存され、GPU メモリの予約が増えるほどエキスパートキャッシュ側に使える量が減ります（`terminal/setup.py:11572-11574`、`terminal/strata_control/setup_config.py:358-368`）。
- 画像読み取りの GPU 用予約量と同時に使う場合は、明示した `N` が既定予約を置換します。必要量より小さくても自動補正はせず、警告を出して指定値を保持します（`terminal/strata_control/setup_config.py:350-366`）。
- 通常の既存モデル起動にこの値を付けると、起動前にモデル設定 JSON を書き換えます。`--setup` を付けた再セットアップでは、同じモデル設定の作り直しに値が使われます（`terminal/setup.py:8577-8589,11761-11775`）。
- `CONTROL` モードで新規構成する場合は専用の `mac_control_setup` / `intel_control_setup` 経路へ分岐します。少なくとも Mac の専用構成生成処理は `write_setup_config(cfg_path, cfg)` を呼び、`a.vram_reserve_mib` の反映を行う箇所は確認できませんでした。その経路での新規構成への適用は確認できていません（`terminal/setup.py:9351-9357,11152-11158,11358-11362,11633-11638`）。
- Apple Silicon のスタンドアロン経路は root parser より先に `engine/metal/setup_mac.py` へ引数をそのまま委譲します。同スクリプトの parser に `--vram-reserve-mib` はなく、同経路でこのオプションが受理されることは確認できません（`terminal/setup.py:9290-9294,11434-11437`、`engine/metal/setup_mac.py:376-401`）。
- `--update` 単独など個々の特殊モードにおける値の適用有無は、本調査では全分岐を網羅していません。上記は通常セットアップと既存モデルの通常起動経路で確認した動作です。

## 出力とエラー

- 負数では parser が `--vram-reserve-mib takes a number of MiB, 0 or more...` をエラーとして出します。整数変換に失敗した場合も `argparse` の引数エラーです（`terminal/setup.py:11643-11644,11572`）。
- 通常の設定生成時および既存モデルの起動前保存時に、予約した MiB 数を知らせる `ok(...)` メッセージを出します。GPU 画像エンコーダーに必要な予約より小さい値では追加の警告があります（`terminal/strata_control/setup_config.py:361-368`、`terminal/setup.py:8588-8589`）。
- parser エラーの終了コードは `argparse` の標準動作に委ねられています。独自の終了コードを設定するコードは確認できませんでした。

## 根拠

- `setup.sh:6-17,81`、`START-HERE.bat:8-17,49-65` — wrapper が `terminal/setup.py` に引数を転送する箇所。
- `terminal/setup.py:11572-11574,11643-11644` — parser 定義、型、既定値の説明、負数 validation。
- `terminal/strata_control/setup_config.py:350-368` — 通常セットアップでの引数追加・画像用予約との置換・警告。
- `terminal/setup.py:8577-8589,11761-11775` — 既存モデル起動時の設定更新と起動分岐。
- `terminal/setup.py:9351-9357,11152-11158,11358-11362,11633-11638` — CONTROL モードの専用セットアップ分岐と Mac 構成保存箇所。
- `terminal/setup.py:7626-7657,7736-7749` — 値の再セットアップ時の引き継ぎ、設定保存とバックアップ。
- `terminal/setup.py:9290-9294,11434-11437`、`engine/metal/setup_mac.py:376-401` — macOS の委譲と委譲先 parser の対象オプション。

