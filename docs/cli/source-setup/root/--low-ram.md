# `--low-ram`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` から委譲） |
| オプション | `--low-ram` |
| 別名 | なし |
| 値 | `auto`、`on`、`off`、`resident`、`mmap` のいずれか。値は必須 |

## 役割

通常は RAM に読み込むモデルの experts を、モデル pack 内の `experts.bin` から扱う low-RAM 起動経路を選びます。GPU が保持しない experts を RAM に常駐させるか、OS のファイルキャッシュ経由で読むかも指定できます。主に、RAM は少ないが大きな GPU を持つ PC で使う設定です。

## 使い方

モデルの設定を開き、resident 方式を明示して、モデル起動をせずに setup する例です。

```sh
./setup.sh --setup --model IQ3_XXS --low-ram resident --no-start
```

`setup.sh` は引数をそのまま `setup.py` に渡します。Windows では同じ parser を `START-HERE.bat` が呼び、`SETUP.bat` は `--setup` を付けて委譲します（`setup.sh:76`、`START-HERE.bat:48,53`、`SETUP.bat:1-3`）。

## 値と既定値

| 値 | ソース上の動作 |
| --- | --- |
| `auto`（既定） | RAM が experts の容量 `arena_gb` と余裕分 10 GB の合計を下回る場合に low-RAM 経路を選びます。それ以外は選びません。 |
| `on` | low-RAM 経路を選びます。resident に必要な RAM があれば resident、足りなければ mmap を選びます。 |
| `off` | low-RAM 経路を無効にします。RAM が不足するモデルでは、ページングのリスクを警告して続行確認します。 |
| `resident` | low-RAM 経路を選び、GPU が保持しない experts を resident としてエンジンに渡します。RAM に収まらない場合、エンジン側が mmap に fallback する可能性がソースコメントに記されています。 |
| `mmap` | low-RAM 経路を選び、GPU が保持しない experts を OS のファイルキャッシュ経由で読む設定をエンジンに渡します。 |

parser は上記以外を受理しません。引数省略時は `auto`、値省略や不正値では `argparse` の usage/error になります。独自の型変換や数値範囲検証はありません。通常の `argparse` のため、同じオプションを複数回指定したときは最後の値が使われます（`setup.py:8523-8527,8553`）。

## 実行時の動作

- `auto` の判定は `RAM < arena_gb + 10 GB` です。`on`、`resident`、`mmap` は明示的に low-RAM を有効にし、`off` は無効にします。ただし `MODELS[model]` に `budget` があるモデルでは、この判定関数は常に無効を返します（`setup.py:5652-5667,5703-5711`）。
- 選択後、GPU の expert cache 見積もりから resident 対象の残り容量を算出します。context と KV cache、MTP の有無、画像 encoder の VRAM 予約がこの見積もりに関係します。`auto` / `on` は残り experts と 10 GB の余裕が RAM に収まる場合に resident を選び、`mmap` は mmap を選びます（`setup.py:5675-5694,9143-9156`）。
- 通常モデルでは設定に応じて `--resident-experts` または `--mmap-experts` をエンジン引数に追加します。low-RAM でも resident でもない場合、RAM 不足時はページングの警告・確認経路に進みます（`setup.py:9043-9044,9439-9440`）。
- 初回に low-RAM 経路を使うモデルで `experts.bin` がまだない場合、setup は GGUF から pack 内に一度だけ同ファイルを作成します。空きディスク容量の見積もりにも experts の容量と 1 GB が加算され、不足時は `fail()` で終了コード 1 になります（`setup.py:9241-9256,9372-9375,825`）。
- UD-Q4_K_XL / UD-IQ4_XS など `budget` モデルでは独自の RAM budget 経路を使います。`auto` / `off` 以外を指定すると「このモデルには適用されない」と警告します。`--low-ram` の resident/mmap 指定がその経路の制御に使われることは確認できません（`setup.py:5709-5711,9026-9030,9430-9438`）。

## 適用条件と相互作用

- 低 RAM の複数 GPU 利用では engine の layer-split 対応が関係します。対応前の engine では setup が全 GPU 利用と 1 GPU 利用を案内し、対話の選択や `--yes` などの条件により 1 GPU に切り替えることがあります。明示的な `--gpus` がある場合は mmap 経路を警告付きで維持する分岐もあります（`setup.py:5653-5661,5751-5783,9031-9037`）。
- Intel Arc 用 `sycl/setup_intel.py` は `--low-ram` が渡されない場合に `--low-ram off` を追加します。指定があれば値を保ったまま共通 setup に渡します（`sycl/setup_intel.py:541-554`）。
- macOS の Control mode は共通 parser の後に `mac_control_setup()` へ分岐しますが、その処理に low-RAM option を使う箇所はありません。Metal 用 `metal/setup_mac.py` は独自 parser を持ち、未知の引数を「Mac では使わない」と警告して無視します。さらに Control mode でない macOS は共通 parser より前に別処理へ渡されます（`setup.py:8418-8419,8561-8562,8236-8242`、`metal/setup_mac.py:356-363`）。macOS の実行経路をこの option の制御対象として扱える根拠は確認できません。
- RAM/GPU の組み合わせが low-RAM モードで動作可能かは別途見積もられます。`--check` とモデル選択時の表示は GPU が保持する比率や RAM/SSD 側に残る方式を示しますが、この option 自体がすべてのハードウェア構成で起動成功を保証するわけではありません（`setup.py:5697-5700,8816-8834,8877-8880`）。

## 出力とエラー

setup は low-RAM の使用、GPU が保持する experts の概算、残りを RAM に置くかファイルキャッシュ経由にするかを `[ok]` 表示し、GPU が experts の 60% 未満しか保持できない場合には SSD 読み込みによる大幅な低速化を警告します。複数 GPU の選択や RAM 不足では追加の案内・確認が出ることがあります（`setup.py:815-823,9157-9176`）。

`--low-ram off` でモデルが RAM に収まらないと、ページングによる遅さや起動失敗の可能性を警告します。確認を拒否した場合はセットアップを停止し、`fail()` が終了コード 1 を返します（`setup.py:5851-5860,5863-5879,825-830`）。

## 根拠

- `setup.py:8523-8527,8553` — parser の値、既定値、help、引数解析。
- `setup.py:5652-5667,5675-5711` — 10 GB の余裕、GPU/ RAM 見積もり、auto と budget モデルの判定。
- `setup.py:9026-9044,9143-9176` — 適用分岐、複数 GPU・RAM 条件、表示と警告。
- `setup.py:9238-9256,9372-9375,9426-9440` — 空き容量判定、`experts.bin` 作成、エンジン引数。
- `setup.py:5851-5879,825-830` — RAM 不足時の確認と失敗処理。
- `setup.sh:76`、`START-HERE.bat:48,53`、`SETUP.bat:1-3`、`update.sh:62`、`UPDATE.bat:79` — wrapper の委譲。
- `sycl/setup_intel.py:541-554`、`metal/setup_mac.py:356-363`、`setup.py:8236-8242,8418-8419,8561-8564` — Intel Arc と macOS の別経路。
- 利用者向け説明: `docs/MODELS.md:95-101`。現行 source の parser と実装を主根拠とし、help は実行していません。
