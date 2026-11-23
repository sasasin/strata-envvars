# `INK_METAL_FORCE_MODEL_FILE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Apple の Metal backend が `ModelSourceKind::Strata` のモデルを読み込むとき、専用の `.strata` loader の代わりに `InkModelFile` を使う共通 loader を選ぶための環境変数である。値の先頭文字が `1` なら共通 loader、そうでなければ専用 loader を使う。モデル形式の選択そのものや CLI オプションの値は変更しない。`MetalInkBackend::init` の分岐で読み取り、専用 loader はファイルを mmap して Section 1 / Section 4 を Metal buffer に包む。共通 loader は `InkModelFile` から Section 1 と expert body を読み、anonymous arena に組み立てる（`engine/src/inkling2/metal/ink_metal_backend.mm:92-108`、`engine/src/inkling2/metal/ink_metal_common.h:448-475, 572-575, 651-762`）。

## 値と判定

`MetalInkBackend::init` が `std::getenv` で値を取得し、文字列全体ではなく `force_mf[0] == '1'` だけを見る。`getenv` が null、空文字、または先頭が `1` 以外なら変数条件は偽。数値 parse、大文字小文字変換、空白除去、末尾の検証はない。したがって `1`, `10`, `1anything` は真で、`0`, `true`, ` 1`, 空文字は偽となる（`engine/src/inkling2/metal/ink_metal_backend.mm:98-103`）。

| 条件 | unset | 共通 loader を選ぶ値 | 専用 `.strata` loader になる値 |
| --- | --- | --- | --- |
| Metal backend、入力 kind が `Strata` | 専用 loader | 先頭文字が `1`（例: `1`, `1suffix`） | 空文字、`0`, `true`, ` 1` など先頭が `1` 以外 |
| 入力 kind が `Safetensors` または `Gguf` | 共通 loader | この変数の値による差なし | 該当なし。この分岐では常に共通 loader |

入力 kind は `InkModelFile::open` が safetensors / GGUF のパスを判定し、それ以外を Strata として設定する（`engine/src/inkling2/ink_manifest.h:454-478`）。

## 有効になる条件

- `APPLE` のときに追加される Metal backend であること（`engine/src/inkling2/CMakeLists.txt:203-205`）。
- 変数で loader の選択が変わるのは `model.kind == ModelSourceKind::Strata` の場合だけ。Safetensors と GGUF は常に共通 loader に進む（`engine/src/inkling2/ink_metal_backend.mm:98-103`）。
- `.strata` 入力でも、先頭文字 `1` でなければ変数は共通 loader を選ばない。別の CLI 引数による同等の loader 選択はこのコードにはない。
- CLI の通常実行と server 実行はいずれもモデルを開いた後に backend の `init` を呼ぶため、この分岐を通る（`engine/src/inkling2/ink_main.cpp:556-568`）。
- `INK_METAL_FORCE_SK_TRANSCODE` は共通 loader 内の別判定であり、この環境変数の loader 選択を置き換えない。Strata kind は GGUF native 条件を満たさないため、同変数の GGUF native 判定は Strata のこの経路を変えない（`engine/src/inkling2/metal/ink_metal_common.h:655-680`）。

## 実行時の詳細

環境変数を読むのは Metal backend の `init` ごとで、関数内 static などへの cache はない。値はこの呼び出し時に一度だけ読み、モデル読み込み後や各リクエストでは再評価しない。実行中にプロセス環境を書き換えた場合の反映タイミングは、その後に別の `init` が呼ばれる場合に限られる（`engine/src/inkling2/metal/ink_metal_backend.mm:92-108`）。

変数が真の Strata 経路では、共通 loader が `InkModelFile::read_section1` / `read_expert_body` 経由で元の Strata reader からデータを取得し、transcode planner を通して expert body を anonymous mmap arena に構築する。変数が偽の場合は専用 loader が Strata ファイルを直接開き、mmap したデータを Metal buffer に包む。どちらも後続の `runner_.init` に失敗があれば `init` は false を返す（`engine/src/inkling2/metal/ink_metal_backend.mm:98-108`、`engine/src/inkling2/ink_manifest.h:520-529`、`engine/src/inkling2/metal/ink_metal_common.h:572-575, 651-762`）。

この変数を読む場所は Strata 所有ソース内で上記 1 箇所だった。動的な env helper を介した参照や、他 backend / server 層での同名参照は見つからなかった。

## ログと測定値

変数の値だけを理由に出す警告・ログはない。loader 成功時、専用経路は `[ink_metal] loaded %s (build=...` の形式で、共通 loader は `[ink_metal] loaded %s (src=%s, build=...` の形式で stderr にロード情報を出す（`engine/src/inkling2/metal/ink_metal_common.h:467-475, 754-762`）。失敗時は backend `init` が false となり、CLI は `init: <error>` を stderr に出して status 1、server は `ERR init: <error>` を返す（`engine/src/inkling2/ink_main.cpp:564-568`）。例として専用 loader は `cannot open <path>`、`invalid .strata file size: <path>`、`mmap failed for <path>` を設定し、共通 loader は anonymous mmap に失敗すると `mmap(MAP_ANON) failed for unified GGUF/safetensors arena (<MiB> MiB)` を設定する（`engine/src/inkling2/metal/ink_metal_common.h:361-369, 448-458, 706-710`）。

`docs/DETAILS.md` にこの変数の個別説明や測定値は見つからなかったため、速度・メモリ差の測定値は記載しない。

## 根拠

- 候補一覧上の掲載: `docs/envvars/000_envvers.md:505`（索引は候補名の確認にのみ使用）。
- 読み取りと loader 分岐: `engine/src/inkling2/metal/ink_metal_backend.mm:92-108`。
- backend の Apple 条件: `engine/src/inkling2/CMakeLists.txt:203-205`。
- 入力 kind の決定: `engine/src/inkling2/ink_manifest.h:454-478`。
- 共通 loader が Section / expert body を読む経路: `engine/src/inkling2/ink_manifest.h:514-529`、`engine/src/inkling2/metal/ink_metal_common.h:651-762`。
- CLI/server の init 結果表示: `engine/src/inkling2/ink_main.cpp:556-568`。
