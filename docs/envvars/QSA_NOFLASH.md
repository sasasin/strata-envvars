# `QSA_NOFLASH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の standalone parity プログラム `qsa_prompt_parity` で、`qsa_flash` の実行と比較検査を飛ばすための診断用スイッチです。Strata エンジンの実行時設定ではありません。対象名のソース全体検索では `metal/tests/qsa_prompt_parity.cpp` の読み取りだけが見つかり、エンジン側の Metal 実装には読み取りがありません。

## 値と判定

| 状態 | `noflash` | 動作 |
|---|---:|---|
| 未設定 | `false` | 通常の parity 検査で `qsa_flash` を実行し、`qsa_attn` + merge の結果と比較する |
| 設定あり | `true` | `qsa_flash` の実行とその比較検査を飛ばす |

値の内容は parse されません。`std::getenv("QSA_NOFLASH") != nullptr` の判定なので、`1` 以外の文字列も空文字も有効です。`main()` 冒頭で一度だけ読み取ります。

## 有効になる条件

このスイッチが参照されるのは `metal/tests/qsa_prompt_parity.cpp` のテストプログラムだけです。Metal 用 CMake は `metal/tests/*.cpp` を parity / benchmark プログラムとして個別 executable にします（`metal/CMakeLists.txt:4-6,41-46`）。通常の `strata` エンジン実行には影響しません。

## 実行時の詳細

テストは `qsa_attn_mm` と `qsa_attn` + merge の比較を行い、その後 `QSA_NOFLASH` が未設定なら `qsa_flash` を実行して相対 L2 誤差を比較します。設定されている場合は、各 `pos0` の行列ユニット比較の直後に次の `pos0` へ進むため、flash の比較行は出力されず、その比較は終了コードの `fails` に加算されません。最後の score 比較はどちらの場合も継続します。

ただし `--bench` を指定した実行では、各位置のベンチマーク処理後にループを抜けるため、`QSA_NOFLASH` による分岐には到達しません。benchmark 出力では `qsa_flash` の計時も行われます。また通常モードでも `qsa_flash` pipeline の作成自体は `noflash` 判定の後、比較ループより前に行われます。

## 根拠

- `metal/tests/qsa_prompt_parity.cpp:23-28`: `main()` 冒頭で環境変数の設定有無を読み、テスト用 Metal ライブラリをコンパイルする。
- `metal/tests/qsa_prompt_parity.cpp:41-45`: 通常の parity 実行でも `qsa_flash` pipeline を作成し、その情報を出力する。
- `metal/tests/qsa_prompt_parity.cpp:72-82`: `--bench` 経路は `qsa_flash` を計時し、環境変数を使う分岐より前にループを抜ける。
- `metal/tests/qsa_prompt_parity.cpp:98-118,158-159`: 通常の検査では `QSA_NOFLASH` が flash 比較とその pass/fail 加算だけを省略し、最終終了コードは残りの検査結果から決まる。
- `metal/CMakeLists.txt:4-6,41-46`: `metal/tests/*.cpp` を standalone parity / benchmark executable としてビルドする。
- `metal/src/engine/window.cpp:2393-2402`: エンジンの別の `qsa_flash` 実行経路。`QSA_NOFLASH` を参照せず、flash 条件に応じて dispatch する。

