# INK_TEST_NO_CHECKPOINT

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-26 時点）。

## 役割

この変数は、GPU を使わない shared-prefix 回帰テスト専用の ink_prefix_mock backend で checkpoint を使えない状態にする。通常の strata-inkling 実行経路で読む箇所は見つからず、ユーザー向け実行時設定ではない。専用ターゲットは CMake オプション STRATA_INK_BUILD_PREFIX_TESTS が有効なときだけ追加され、このオプションの既定値は OFF（engine/src/inkling2/CMakeLists.txt:289-297）。

mock ではこの変数が設定されていると supports_shared_checkpoint() が false を返し、共有 checkpoint 対応を示すプロトコル情報が shared_prefix=0 になる。また prompt/shared の両 checkpoint 保存処理が失敗を返す。これにより回帰テストは shared-prefix を再利用できない場合の prefill fallback を確認する。これは mock とテスト scheduler 上の動作であり、実 backend の checkpoint 可否や挙動を表すものではない（engine/src/inkling2/ink_prefix_mock.cpp:13-18,40-44; engine/src/inkling2/ink_serve.h:562-567,1112-1123; engine/src/inkling2/test_shared_prefix.py:151-157,181-185）。

## 値と判定

C++ の std::getenv が返すポインタの有無だけを判定し、値は parse しない。したがって未設定なら無効、空文字を含め何らかの値が設定されていれば有効である。0、false、0anything、大文字小文字、前後の空白も区別されず、すべて設定ありとして扱う（engine/src/inkling2/ink_prefix_mock.cpp:15,42）。

| 条件 | unset | 設定あり（例） | 判定に使われない値の内容 |
|---|---|---|---|
| ink_prefix_mock | checkpoint 保存を試み、shared checkpoint 対応を報告する | 空文字、0、1、false、0anything のいずれでも保存を失敗させ、shared checkpoint 非対応を報告する | 文字列の内容、数値としての妥当性、大文字小文字、空白 |

## 有効になる条件

- STRATA_INK_BUILD_PREFIX_TESTS=ON でビルドされた ink_prefix_mock を使う必要がある。この専用ターゲットは既定ではビルド対象に追加されない（engine/src/inkling2/CMakeLists.txt:289-297）。
- Python の回帰 harness は親プロセスの環境をコピーして子プロセスを起動する。no_checkpoint=True の場合は子プロセス用環境に 1 を設定する。False の場合も既存の INK_TEST_NO_CHECKPOINT を削除しないため、親環境ですでに設定されていれば無効化されない（engine/src/inkling2/test_shared_prefix.py:13-19）。
- CLI 引数や別の環境変数による上書きは、この変数の読み取り箇所にはない。

## 実行時の詳細

環境値は ink_prefix_mock 内で std::getenv を呼ぶたびに参照され、値のキャッシュはない。プロセス起動後に環境を変更した場合の外部からの反映を定める処理はない。Python harness は子プロセス起動前に環境辞書を作る（engine/src/inkling2/ink_prefix_mock.cpp:13-18,40-44; engine/src/inkling2/test_shared_prefix.py:13-19）。

変数が設定されると mock の prompt checkpoint 保存（save_prompt_checkpoint）と shared checkpoint 保存（save_shared_checkpoint）はどちらも false を返す。scheduler は保存が成功した場合だけ対応する prefix を保持するため、この mock では checkpoint prefix は保持されない。shared checkpoint は再利用できず、テストは次の異なる prompt の reuse が 0 になることを確認する。なお supports_shared_checkpoint() は INFO の能力表示に使われるが、scheduler 内の保存・復元呼び出しを直接 gate してはいない。変数を読んで保存を失敗させる mock 側の分岐が結果を作る（engine/src/ink_prefix_mock.cpp:13-18,40-44; engine/src/ink_serve.h:562-567,690-713,1112-1123; engine/src/inkling2/test_shared_prefix.py:151-157,181-185）。

## ログと測定値

専用 mock のプロトコル INFO 行に shared_prefix=0（変数あり）または shared_prefix=1（変数なし）が出る。警告やエラー文を出す分岐はこの変数の読み取り処理にはない。回帰テストは非対応時の reuse が 0 であることと INFO の値を assert するが、この調査ではテストを実行していない（engine/src/inkling2/ink_serve.h:562-568; engine/src/inkling2/test_shared_prefix.py:151-157,181-185）。

## 根拠

- engine/src/inkling2/ink_prefix_mock.cpp:13-18,40-44 — 設定有無の判定、prompt/shared checkpoint 保存、対応能力の報告。
- engine/src/inkling2/CMakeLists.txt:289-297 — 専用 mock/harness のビルド条件（既定 OFF）。
- engine/src/inkling2/test_shared_prefix.py:13-19,151-157,181-185 — 子プロセスへの値設定・継承と fallback/INFO の回帰確認。
- engine/src/inkling2/ink_serve.h:562-568,690-713,1112-1123 — INFO 表示、shared checkpoint の復元候補選択、保存結果が scheduler prefix に反映される条件。
