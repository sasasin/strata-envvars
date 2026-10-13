# `STRATA_CHECK_SWAPS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL の `strata generate` にある resident RAM mode の adaptive tier swap を検査する診断用フックです。通常の推論設定ではなく、入れ替えで GPU cache から退避した expert のバイト列が元の model file と一致するか、実行後に expert の保持状態と RAM copy の内容が整合しているかをログに出します。リポジトリ全体の完全一致検索では、環境変数を読む実装は `sycl/src/program/generate.cpp` の2箇所だけです。

## 値と判定

どちらの読み取り箇所も `std::getenv()` の結果を文字列全体として parse せず、次の条件で有効・無効を決めます。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（`getenv()` が null） |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `0` | 無効（例: `0`, `0anything`） |
| それ以外の非空文字列 | 有効（例: `1`, `true`, `false`, `2`, `x`） |

大文字小文字、空白、数値としての妥当性、文字列全体は検査されません。値は関数内で都度読み取られ、`static` cache には保存されません。そのため、各検査が呼ばれる時点でのプロセス環境が判定に使われます（実行中に環境を変更するコードは確認できません）。

根拠: `sycl/src/program/generate.cpp:363,12599`。

## 有効になる条件

- swap 中の検査は `FileExpertSource::complement_ready()` が true で、adaptive tier に swap があり、実際に交換用 buffer へ退避する expert が staging 対象になった場合に限り評価されます。resident RAM mode でない場合、swap が空の場合、または対象 swap がない場合は検査されません。
- 実行後の監査も `src.complement_ready()` が true の場合だけ行われます。
- 本番ソースで確認できるのは SYCL 側の `generate.cpp` です。CUDA/HIP の同名動作はこの commit の完全一致検索では見つかりません。

## 実行時の詳細

### Swap ごとの退避内容検査

`resident_stage_swaps()` は、GPU cache だけが保持している退避対象 expert の bytes を owning device の stream から exchange buffer にコピーし、stream の完了を待ちます。その後、環境変数が有効なら `copy_blob_from_file()` で model file(s) から参照 bytes を読み、exchange buffer と `memcmp()` で比較します。参照読み込みに失敗した場合も「異なる」として数えます。

不一致ごとに stderr へ `strata: STRATA_CHECK_SWAPS: layer %d expert %d: the exchange buffer differs from the file` を出し、各 batch の集計として `%zu staged, %lld differ (total %lld ok, %lld differ)` を出します。ここでの差異や参照読込失敗は記録されますが、そのこと自体では swap を中止しません。続けて `stage_exchange()` を呼びます。実際の適応 swap からは serve 側と通常 generate 側の双方で `resident_stage_swaps()` が呼ばれます。

根拠: `sycl/src/program/generate.cpp:318-323,336-386,7903-7912,12253-12256`; `sycl/include/strata/core/expert_source.hpp:573-577`。

### 実行後の保持状態と RAM 内容監査

生成処理の終了付近で、resident RAM mode かつ環境変数が有効なら全 layer/expert を走査します。expert が RAM にも GPU cache にもない数を `held by neither` として数え、RAM copy がある expert については model file(s) の bytes と比較し、不一致数を数えます。不一致の詳細は最大8件 stderr に出し、集計を stdout に `STRATA_CHECK_SWAPS ... audit: ...` として出力します。

この監査は結果を表示するもので、`lost` や `stale` が0でない場合に終了コードを変更したり処理を失敗させたりする分岐はありません。どちらの検査もファイルから参照 bytes を読むため、診断が有効な実行では追加の読み込みと比較処理が発生します。

根拠: `sycl/src/program/generate.cpp:12592-12620`。

## 文書との照合

`docs/DETAILS.md` および `docs/` 内に `STRATA_CHECK_SWAPS` の説明は見つかりませんでした。性能値や正確性の測定結果はこの変数について記載していません。
