# `STRATA_INK_KEEP_MAPPED_PAGES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 の共通 GGUF ローダーが、GGUF の読み取り専用マッピングからコピーし終えた範囲のページを OS に返す処理を止める。既定ではページ返却を試み、環境変数の値の先頭文字が `1` の場合はページを保持する。通常の生成計算や重みの変換を切り替える変数ではなく、Strata 所有の `release_mapped_pages` が呼ばれた範囲にだけ作用する（`engine/include/strata/core/mapped_pages.hpp:25-44`、`engine/src/inkling2/ink_gguf_loader.h:864-868,1036-1064`）。

共通 `InkModelFile` は CPU / CUDA / HIP / Metal / SYCL の各 backend で共有される。対象処理はこの共通ローダーで GGUF を開いた場合に限られ、Safetensors と `.strata` の読み込み経路はこの変数を参照しない（`engine/src/inkling2/ink_manifest.h:440-442,462-477,524-533`）。

## 値と判定

`std::getenv` で取得し、値全体の parse はせず、最初の1文字が ASCII `1` かを判定する。`keep_mapped_pages()` の関数内 `static const bool` に初回結果を保存する（`engine/include/strata/core/mapped_pages.hpp:25-27`）。

| 条件 | unset | ページを保持する値の例 | ページ返却を試みる値の例 |
|---|---|---|---|
| 全 OS（共通 GGUF ローダー） | 保持しない | `1`, `10`, `1anything` | 空文字, `0`, `01`, `true`, `false`, `0anything`, ` 1` |

大文字小文字、空白、数値としての妥当性、後続文字は検査しない。従って `true` は有効な真値として扱われず、空文字も保持指定ではない。先頭が `1` であれば後ろの文字列にかかわらず保持する（同 `mapped_pages.hpp:25-27`）。

## 有効になる条件

- Inkling-2 の共通 `InkModelFile` が GGUF 形式を選び、`GgufAdapter::open_into` または同 adapter の `read_expert_body` がページ返却関数を呼ぶこと（`engine/src/inkling2/ink_manifest.h:468-472,530-533`、`engine/src/inkling2/ink_gguf_loader.h:864-868,988-1064`）。
- GGUF のモデルオープン後は、trunk・drafter・vision tensor のコピー後に `_exps` 名を含まない tensor の範囲が対象になる。専門家 tensor は、専門家本体を個別にコピーまたは再パックしたとき、その gate/up/down 範囲が対象になる（`engine/src/inkling2/ink_gguf_loader.h:864-868,998-1040,1043-1065`）。
- 対象範囲に `nullptr`、長さ 0、または内側に丸めた全ページがなければ、環境変数が未設定でも何も返さない（`engine/include/strata/core/mapped_pages.hpp:32-37`）。
- この名前を読む CLI 引数、別環境変数による上書き、サーバーモード固有の判定は見つからない。GGUF adapter の経路以外ではこの helper が呼ばれないため、その経路では値に効果がない（`engine/src/inkling2/ink_manifest.h:462-477,524-533`）。

## 実行時の詳細

GGUF reader はモデルファイルを読み取り専用でマップする（Windows は `CreateFileMappingA` / `MapViewOfFile`、それ以外は `mmap`。`engine/include/strata/artifact/gguf_reader.hpp:447-479`）。ローダーは読み取ったテンソル範囲をコピーした後、ページ返却 helper を呼ぶ。全体のモデルオープン時には `_exps` を含む tensor を除外し、専門家データは `read_expert_body` のコピーまたは NVFP4 から SF4 への再パック後に対象範囲を渡す（`engine/src/inkling2/ink_gguf_loader.h:864-868,998-1040,1053-1065`）。

helper は固定 4096 byte 境界に内側丸めして、範囲内に完全に含まれるページだけを扱う。`STRATA_INK_KEEP_MAPPED_PAGES` の判定結果は helper の最初の実呼び出しでキャッシュされ、同一プロセス内の後続呼び出しでは環境を読み直さない。したがって、最初の呼び出し後に環境を変更しても反映されない（`engine/include/strata/core/mapped_pages.hpp:25-37`）。

先頭文字が `1` でなければ、Windows では `VirtualUnlock`、Windows 以外では `madvise(..., MADV_DONTNEED)` を実行する。Windows 分岐は `VirtualUnlock` の結果にかかわらず範囲長を返し、非 Windows 分岐は `madvise` 成功時だけ範囲長を返す。いずれもこの helper の戻り値は全呼び出し箇所で無視されるため、返却に失敗しても GGUF 読み込みの成功・失敗判定は変わらない（`engine/include/strata/core/mapped_pages.hpp:38-44`、`engine/src/inkling2/ink_gguf_loader.h:864-868,1036-1039,1062-1064`）。

## ログと測定値

この環境変数の判定やページ返却の成否を報告するログはなく、戻り値も呼び出し元で使われない。環境変数を設定してページ保持を選んだ場合も、helper 自身からは stdout / stderr に出力しない（`engine/include/strata/core/mapped_pages.hpp:25-44`、`engine/src/inkling2/ink_gguf_loader.h:864-868,1036-1039,1062-1064`）。この変数の効果に関する測定値は、調査対象のソースおよび `docs/DETAILS.md` では確認できなかった。

## 根拠

- 読み取りと初回キャッシュ、ページ範囲判定、OS ごとの処理: `engine/include/strata/core/mapped_pages.hpp:25-44`
- GGUF / Safetensors / `.strata` の選択と共通 reader の振り分け: `engine/src/inkling2/ink_manifest.h:440-477,524-533`
- GGUF ファイルの read-only mapping: `engine/include/strata/artifact/gguf_reader.hpp:447-479`
- コピー後の trunk tensor と専門家ページの返却箇所: `engine/src/inkling2/ink_gguf_loader.h:864-868,988-1065`
